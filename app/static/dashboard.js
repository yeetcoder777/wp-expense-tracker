const tokenKey = 'ledger-dashboard-token';
const state = { importPreview: null, currenciesLoaded: false };
const tokenDialog = document.querySelector('#token-dialog');
const connection = document.querySelector('#connection');
const toastElement = document.querySelector('#toast');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function money(amount, currency = 'INR') {
  const number = Number(amount || 0);
  return `${escapeHtml(currency)} ${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function notify(message, error = false) {
  toastElement.textContent = message;
  toastElement.style.background = error ? '#843b34' : '#1b3025';
  toastElement.classList.add('visible');
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => toastElement.classList.remove('visible'), 3200);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = sessionStorage.getItem(tokenKey);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) {
      connection.textContent = '● Access expired';
      connection.className = 'connection error';
      if (!tokenDialog.open) tokenDialog.showModal();
    }
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return response;
}

async function getJson(path, options) {
  return (await api(path, options)).json();
}

function setConnected(value) {
  connection.textContent = value ? '● Connected' : '● Not connected';
  connection.className = value ? 'connection connected' : 'connection';
}

function currentMonthValue() {
  const now = new Date();
  const localMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  return document.querySelector('#report-month').value || localMonth;
}

async function loadReport() {
  if (!state.currenciesLoaded) await loadCurrencies();
  const [year, month] = currentMonthValue().split('-').map(Number);
  const currency = document.querySelector('#report-currency').value || 'INR';
  const data = await getJson(`/api/reports/monthly?year=${year}&month=${month}&currency=${encodeURIComponent(currency)}`);
  const report = data.current;
  const previous = data.previous;
  const reportTitle = new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  document.querySelector('#report-title').textContent = reportTitle;
  const change = data.expense_change_percent;
  const compareNote = change === null ? 'No prior-period spending to compare' : `${Math.abs(Number(change)).toFixed(1)}% ${Number(change) > 0 ? 'higher' : Number(change) < 0 ? 'lower' : 'unchanged'} than the previous period`;
  const stats = [
    ['Income', report.income, report.currency, 'Money received in this period'],
    ['Expenses', report.expenses, report.currency, compareNote],
    ['Net balance', report.net, report.currency, Number(report.net) >= 0 ? 'Income less expenses' : 'Expenses exceed income'],
    ['Savings rate', `${Number(report.savings_rate).toFixed(1)}%`, '', `Previous period: ${money(previous.net, previous.currency)} net`],
  ];
  document.querySelector('#report-stats').innerHTML = stats.map(([label, value, currency, note]) => {
    const amount = typeof value === 'number' || /^-?\d+(\.\d+)?$/.test(String(value)) ? money(value, currency) : escapeHtml(value);
    const tone = label === 'Net balance' ? (Number(report.net) >= 0 ? 'positive' : 'negative') : '';
    return `<article class="stat-card"><div class="stat-label">${escapeHtml(label)}</div><div class="stat-value ${tone}">${amount}</div><div class="stat-note">${escapeHtml(note)}</div></article>`;
  }).join('');

  const maxCategory = Math.max(...report.categories.map((item) => Number(item.amount)), 1);
  document.querySelector('#category-chart').innerHTML = report.categories.length
    ? report.categories.map((item) => `<div class="chart-row"><span class="chart-label">${escapeHtml(item.category)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, Number(item.amount) / maxCategory * 100)}%"></div></div><span class="chart-value">${money(item.amount, report.currency)}</span></div>`).join('')
    : '<p class="empty-state">No expenses in this period yet.</p>';
  document.querySelector('#largest-expenses').innerHTML = report.largest_expenses.length
    ? report.largest_expenses.map((item) => `<div class="simple-list-row"><div><strong>${escapeHtml(item.purpose || 'Unspecified')}</strong><small>${escapeHtml(item.transaction_date || 'Date not set')} · ${escapeHtml(item.category || 'other')} · #${escapeHtml(item.id)}</small></div><strong>${money(item.amount, item.currency)}</strong></div>`).join('')
    : '<p class="empty-state">No expenses in this period yet.</p>';
  setConnected(true);
}

async function loadCurrencies() {
  const currencies = await getJson('/api/transactions/currencies');
  state.currenciesLoaded = true;
  for (const select of document.querySelectorAll('[data-currency-select]')) {
    const current = select.value || (select.dataset.allowAll ? '' : 'INR');
    const options = [...new Set(['INR', ...currencies])];
    select.innerHTML = `${select.dataset.allowAll ? '<option value="">All currencies</option>' : ''}${options.map((currency) => `<option value="${escapeHtml(currency)}">${escapeHtml(currency)}</option>`).join('')}`;
    select.value = select.dataset.allowAll && current === '' ? '' : options.includes(current) ? current : options[0];
  }
}

function queryFromForm(form) {
  const params = new URLSearchParams();
  for (const [key, value] of new FormData(form)) {
    if (String(value).trim()) params.set(key, String(value).trim());
  }
  return params.toString();
}

async function loadTransactions(form = document.querySelector('#transaction-filters')) {
  const query = queryFromForm(form);
  const items = await getJson(`/api/transactions?limit=200${query ? `&${query}` : ''}`);
  const body = document.querySelector('#transactions-body');
  document.querySelector('#transaction-empty').classList.toggle('hidden', items.length > 0);
  body.innerHTML = items.map((item) => `<tr>
    <td>${escapeHtml(item.transaction_date || '—')}</td>
    <td><strong>${escapeHtml(item.purpose || 'Unspecified')}</strong><div class="muted">${escapeHtml(item.person || '')} · #${escapeHtml(item.id)}</div></td>
    <td>${escapeHtml(item.category || 'other')}</td>
    <td><span class="type-pill type-${escapeHtml(item.transaction_type)}">${escapeHtml(item.transaction_type)}</span></td>
    <td class="align-right">${money(item.amount, item.currency)}</td>
    <td><div class="row-actions"><button class="text-button" data-edit="${item.id}">Edit</button><button class="text-button delete" data-delete="${item.id}">Delete</button></div></td>
  </tr>`).join('');
}

async function loadBudgets() {
  const budgets = await getJson('/api/budgets');
  const list = document.querySelector('#budget-list');
  list.innerHTML = budgets.length ? budgets.map((budget) => {
    const percent = Number(budget.percent_used);
    return `<article class="card budget-card ${percent >= 100 ? 'over' : ''}"><div class="budget-card-head"><div><div class="budget-title">${escapeHtml(budget.category === 'all' ? 'Overall spending' : budget.category)}</div><div class="budget-amount">Limit ${money(budget.amount, budget.currency)}</div></div><button class="text-button delete" data-budget-delete="${budget.id}">Remove</button></div><div class="progress-track"><div class="progress-fill" style="width:${Math.min(100, percent)}%"></div></div><div class="budget-meta"><span>${money(budget.spent, budget.currency)} spent · ${percent.toFixed(0)}%</span><span>${money(budget.remaining, budget.currency)} left</span></div></article>`;
  }).join('') : '<article class="card empty-state">No budgets yet. Add one to get monthly progress and WhatsApp alerts at 80% and 100%.</article>';
}

async function loadRecurring() {
  const schedules = await getJson('/api/recurring');
  const list = document.querySelector('#recurring-list');
  list.innerHTML = schedules.length ? schedules.map((item) => `<article class="card schedule-card"><div class="schedule-main"><strong>${escapeHtml(item.name)} · ${money(item.amount, item.currency)}</strong><p>${escapeHtml(item.transaction_type)} · ${escapeHtml(item.interval)} · next ${escapeHtml(item.next_run_date)} · ${item.auto_record ? 'auto-record' : 'reminder only'} · ${item.is_active ? 'active' : 'paused'}</p></div><div class="schedule-actions"><button class="text-button" data-schedule-toggle="${item.id}" data-active="${item.is_active}">${item.is_active ? 'Pause' : 'Resume'}</button><button class="text-button delete" data-schedule-delete="${item.id}">Delete</button></div></article>`).join('') : '<article class="card empty-state">No recurring transactions yet.</article>';
}

function showImportPreview(preview) {
  state.importPreview = preview;
  const card = document.querySelector('#import-preview');
  card.classList.remove('hidden');
  const duplicateCount = preview.transactions.filter((item) => item.possible_duplicate).length;
  document.querySelector('#import-summary').textContent = `${preview.transactions.length} transaction(s) from ${preview.source_name}. ${duplicateCount ? `${duplicateCount} possible duplicate(s) are unchecked by default.` : 'Review the details before importing.'}`;
  document.querySelector('#import-errors').innerHTML = preview.errors?.length
    ? `<div class="error-box">${preview.errors.map((error) => `Row ${error.row}: ${escapeHtml(error.error)}`).join('<br>')}</div>` : '';
  document.querySelector('#import-body').innerHTML = preview.transactions.map((item, index) => `<tr class="${item.possible_duplicate ? 'duplicate-row' : ''}">
    <td><input type="checkbox" data-import-index="${index}" ${item.possible_duplicate ? '' : 'checked'} aria-label="Include transaction ${index + 1}"></td>
    <td>${escapeHtml(item.transaction_date || '—')}</td><td>${escapeHtml(item.purpose || item.person || 'Unspecified')}${item.possible_duplicate ? '<div class="muted">Possible duplicate</div>' : ''}</td><td>${escapeHtml(item.category || 'other')}</td><td>${escapeHtml(item.transaction_type)}</td><td class="align-right">${money(item.amount, item.currency)}</td>
  </tr>`).join('');
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function previewUpload(form, endpoint) {
  const file = new FormData(form).get('file');
  if (!file || !file.size) throw new Error('Choose a file first.');
  const data = new FormData();
  data.append('file', file);
  const preview = await getJson(endpoint, { method: 'POST', body: data });
  showImportPreview(preview);
}

async function loadPanel(panel) {
  if (panel === 'overview') await loadReport();
  if (panel === 'transactions') await loadTransactions();
  if (panel === 'budgets') await loadBudgets();
  if (panel === 'recurring') await loadRecurring();
}

document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', async () => {
  document.querySelectorAll('.tab').forEach((item) => item.classList.toggle('active', item === button));
  document.querySelectorAll('.panel').forEach((item) => item.classList.toggle('active', item.id === `panel-${button.dataset.panel}`));
  try { await loadPanel(button.dataset.panel); } catch (error) { notify(error.message, true); }
}));

document.querySelector('#settings-button').addEventListener('click', () => tokenDialog.showModal());
document.querySelector('#token-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const token = new FormData(event.currentTarget).get('token').trim();
  sessionStorage.setItem(tokenKey, token);
  document.querySelector('#token-error').textContent = '';
  try {
    await loadReport();
    tokenDialog.close();
    notify('Dashboard connected.');
  } catch (error) {
    sessionStorage.removeItem(tokenKey);
    document.querySelector('#token-error').textContent = error.message;
    setConnected(false);
  }
});

document.querySelector('#report-month').value = currentMonthValue();
document.querySelector('#report-month').addEventListener('change', () => loadReport().catch((error) => notify(error.message, true)));
document.querySelector('#report-currency').addEventListener('change', () => loadReport().catch((error) => notify(error.message, true)));
document.querySelector('#transaction-filters').addEventListener('submit', (event) => {
  event.preventDefault();
  loadTransactions(event.currentTarget).catch((error) => notify(error.message, true));
});
document.querySelector('#transaction-filters').addEventListener('reset', () => setTimeout(() => loadTransactions().catch((error) => notify(error.message, true)), 0));

document.querySelector('#transactions-body').addEventListener('click', async (event) => {
  const editButton = event.target.closest('[data-edit]');
  const deleteButton = event.target.closest('[data-delete]');
  try {
    if (editButton) {
      const id = editButton.dataset.edit;
      const current = await getJson(`/api/transactions/${id}`);
      const amount = prompt(`New amount for transaction #${id}`, current.amount);
      if (amount === null) return;
      const category = prompt('Category', current.category || 'other');
      if (category === null) return;
      const transactionDate = prompt('Date (YYYY-MM-DD)', current.transaction_date || '');
      if (transactionDate === null) return;
      const purpose = prompt('Description', current.purpose || '');
      if (purpose === null) return;
      await getJson(`/api/transactions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ amount, category, transaction_date: transactionDate || null, purpose }),
      });
      notify(`Transaction #${id} updated.`);
      await Promise.all([loadTransactions(), loadReport(), loadBudgets()]);
    }
    if (deleteButton && confirm(`Delete transaction #${deleteButton.dataset.delete}?`)) {
      await api(`/api/transactions/${deleteButton.dataset.delete}`, { method: 'DELETE' });
      notify('Transaction deleted.');
      await Promise.all([loadTransactions(), loadReport(), loadBudgets()]);
    }
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#undo-button').addEventListener('click', async () => {
  if (!confirm('Undo the most recently recorded transaction?')) return;
  try {
    const removed = await getJson('/api/transactions/undo', { method: 'POST' });
    notify(`Undid transaction #${removed.id}.`);
    await Promise.all([loadTransactions(), loadReport(), loadBudgets()]);
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#budget-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  values.amount = String(values.amount);
  try {
    await getJson('/api/budgets', { method: 'POST', body: JSON.stringify(values) });
    event.currentTarget.reset();
    event.currentTarget.elements.currency.value = 'INR';
    await loadBudgets();
    notify('Budget saved.');
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#budget-list').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-budget-delete]');
  if (!button || !confirm('Remove this budget?')) return;
  try { await api(`/api/budgets/${button.dataset.budgetDelete}`, { method: 'DELETE' }); await loadBudgets(); notify('Budget removed.'); }
  catch (error) { notify(error.message, true); }
});

document.querySelector('#recurring-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  values.amount = String(values.amount);
  values.reminder_days = Number(values.reminder_days);
  values.auto_record = form.elements.auto_record.checked;
  try {
    await getJson('/api/recurring', { method: 'POST', body: JSON.stringify(values) });
    form.reset();
    form.elements.currency.value = 'INR';
    form.elements.category.value = 'bills';
    form.elements.reminder_days.value = '1';
    await loadRecurring();
    notify('Recurring schedule added.');
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#recurring-list').addEventListener('click', async (event) => {
  const toggle = event.target.closest('[data-schedule-toggle]');
  const remove = event.target.closest('[data-schedule-delete]');
  try {
    if (toggle) {
      await getJson(`/api/recurring/${toggle.dataset.scheduleToggle}`, { method: 'PATCH', body: JSON.stringify({ is_active: toggle.dataset.active !== 'true' }) });
      await loadRecurring();
      notify('Schedule updated.');
    }
    if (remove && confirm('Delete this recurring schedule?')) {
      await api(`/api/recurring/${remove.dataset.scheduleDelete}`, { method: 'DELETE' });
      await loadRecurring();
      notify('Schedule deleted.');
    }
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#csv-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await previewUpload(event.currentTarget, '/api/imports/csv/preview'); }
  catch (error) { notify(error.message, true); }
});
document.querySelector('#receipt-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await previewUpload(event.currentTarget, '/api/imports/receipt/preview'); }
  catch (error) { notify(error.message, true); }
});

document.querySelector('#confirm-import').addEventListener('click', async () => {
  if (!state.importPreview) return;
  const selected = [...document.querySelectorAll('[data-import-index]:checked')]
    .map((checkbox) => state.importPreview.transactions[Number(checkbox.dataset.importIndex)])
    .map(({ possible_duplicate, ...transaction }) => transaction);
  if (!selected.length) { notify('Select at least one transaction to import.', true); return; }
  const selectedHasDuplicates = [...document.querySelectorAll('[data-import-index]:checked')]
    .some((checkbox) => state.importPreview.transactions[Number(checkbox.dataset.importIndex)].possible_duplicate);
  try {
    const result = await getJson('/api/imports/confirm', {
      method: 'POST',
      body: JSON.stringify({ transactions: selected, source_name: state.importPreview.source_name, skip_possible_duplicates: !selectedHasDuplicates }),
    });
    state.importPreview = null;
    document.querySelector('#import-preview').classList.add('hidden');
    const alertMessage = result.budget_alerts?.length ? ` Budget: ${result.budget_alerts.join(' ')}` : '';
    notify(`Imported ${result.imported}; skipped ${result.skipped_duplicates} duplicate(s).${alertMessage}`);
    state.currenciesLoaded = false;
    await loadCurrencies();
    await Promise.all([loadReport(), loadBudgets(), loadTransactions()]);
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#range-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const report = await getJson(`/api/reports/range?${new URLSearchParams(values)}`);
    document.querySelector('#range-result').innerHTML = `<div class="range-summary"><span>Income <strong>${money(report.income, report.currency)}</strong></span><span>Expenses <strong>${money(report.expenses, report.currency)}</strong></span><span>Net <strong>${money(report.net, report.currency)}</strong></span><span>Savings rate <strong>${Number(report.savings_rate).toFixed(1)}%</strong></span></div>`;
  } catch (error) { notify(error.message, true); }
});

document.querySelector('#export-button').addEventListener('click', async () => {
  try {
    const response = await api('/api/transactions/export/csv');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'transactions.csv';
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) { notify(error.message, true); }
});

if (sessionStorage.getItem(tokenKey)) {
  loadReport().catch((error) => {
    sessionStorage.removeItem(tokenKey);
    setConnected(false);
    if (!tokenDialog.open) tokenDialog.showModal();
    document.querySelector('#token-error').textContent = error.message;
  });
} else {
  tokenDialog.showModal();
}
