/* WhatsApp proof establishes an HttpOnly server session; no browser bearer token. */
(() => {
  const dialog = document.querySelector('#account-dialog');
  const errorBox = document.querySelector('#login-error');
  const form = document.querySelector('#login-form');
  const instructions = document.querySelector('#login-instructions');
  const button = document.querySelector('#login-start-button');
  let challenge = null;
  let timer = null;
  let generation = 0;
  let account = null;

  async function request(path, body) {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Ledger-Request': '1' },
      body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store',
    });
    const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Sign-in failed (${response.status})`);
    return data;
  }

  function stopPolling() {
    generation += 1;
    window.clearTimeout(timer);
    challenge = null;
  }

  function showLogin(message = '', { resetPhone = false } = {}) {
    const wasSignedIn = account !== null;
    stopPolling();
    account = null;
    window.ledgerAuth.account = null;
    document.querySelector('#dashboard-content').classList.add('hidden');
    document.querySelector('#logout-button').classList.add('hidden');
    document.querySelector('#settings-button').textContent = 'Sign in';
    if (resetPhone || wasSignedIn) form.reset();
    form.classList.remove('hidden');
    instructions.classList.add('hidden');
    document.querySelector('#login-command').textContent = '';
    document.querySelector('#login-whatsapp-link').removeAttribute('href');
    errorBox.textContent = message;
    if (wasSignedIn) window.dispatchEvent(new Event('ledger:signedout'));
    if (!dialog.open) {
      dialog.showModal();
      document.querySelector('#login-phone').focus();
    }
  }

  function signedIn(value) {
    stopPolling();
    account = value;
    window.ledgerAuth.account = value;
    document.querySelector('#dashboard-content').classList.remove('hidden');
    document.querySelector('#logout-button').classList.remove('hidden');
    document.querySelector('#settings-button').textContent = value.whatsapp_number;
    document.querySelector('#login-command').textContent = '';
    document.querySelector('#login-whatsapp-link').removeAttribute('href');
    dialog.close();
    window.dispatchEvent(new CustomEvent('ledger:signedin', { detail: value }));
  }

  async function poll(currentGeneration) {
    if (!challenge || generation !== currentGeneration) return;
    if (Date.now() >= Date.parse(challenge.expires_at)) {
      showLogin('This code expired. Please request another one.');
      return;
    }
    try {
      const data = await request('/api/auth/login/complete', {
        request_id: challenge.request_id, poll_secret: challenge.poll_secret,
      });
      if (generation !== currentGeneration) return;
      if (data.status === 'authenticated') { signedIn(data.account); return; }
      timer = window.setTimeout(() => poll(currentGeneration), 3000);
    } catch (error) {
      if (generation === currentGeneration) showLogin(error.message);
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    stopPolling();
    const currentGeneration = generation;
    button.disabled = true;
    errorBox.textContent = '';
    const phone = document.querySelector('#login-phone').value.trim();
    try {
      const started = await request('/api/auth/login/start', { phone });
      if (generation !== currentGeneration) return;
      challenge = started;
      document.querySelector('#login-number').textContent = phone;
      document.querySelector('#login-command').textContent = started.command;
      document.querySelector('#login-whatsapp-link').href = started.whatsapp_url;
      form.classList.add('hidden');
      instructions.classList.remove('hidden');
      document.querySelector('#login-status').textContent = 'Waiting for your WhatsApp message. This code expires in a few minutes.';
      timer = window.setTimeout(() => poll(currentGeneration), 2000);
    } catch (error) {
      if (generation === currentGeneration) errorBox.textContent = error.message;
    } finally { button.disabled = false; }
  });

  document.querySelector('#login-copy-button').addEventListener('click', async () => {
    if (!challenge) return;
    try {
      await navigator.clipboard.writeText(challenge.command);
      document.querySelector('#login-status').textContent = 'Copied. Send the command to the bot from your WhatsApp account.';
    } catch { errorBox.textContent = 'Copy the command above and send it to the bot.'; }
  });
  document.querySelector('#login-restart-button').addEventListener('click', () => showLogin('', { resetPhone: true }));
  document.querySelector('#settings-button').addEventListener('click', () => {
    if (!account && !dialog.open) dialog.showModal();
  });
  document.querySelector('#logout-button').addEventListener('click', async () => {
    try {
      await request('/api/auth/logout', {});
      showLogin('', { resetPhone: true });
    } catch (error) { window.alert('Could not sign out: ' + error.message); }
  });
  dialog.addEventListener('cancel', (event) => event.preventDefault());
  window.ledgerAuth = { account: null, expire: showLogin };
  sessionStorage.removeItem('ledger-dashboard-token');
  // Delay until the dashboard's deferred script has registered its listeners.
  document.addEventListener('DOMContentLoaded', async () => {
    try { signedIn(await request('/api/auth/me')); }
    catch (error) { showLogin(error.message.includes('Sign in') ? '' : error.message); }
  });
})();
