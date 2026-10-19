export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}
function describe(detail, status) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail))
    return detail.map((item) => `${item.loc?.at(-1) || 'Input'}: ${item.msg}`).join('. ');
  return `The request could not be completed (${status}).`;
}
export async function request(path, { body, accountId, signal, ...options } = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('X-Ledger-Request', '1');
  if (body !== undefined && !(body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  const combined = signal ? AbortSignal.any([signal, controller.signal]) : controller.signal;
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: 'same-origin',
      cache: 'no-store',
      signal: combined,
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError('The connection took too long or is unavailable. Please try again.', 0);
  } finally {
    clearTimeout(timer);
  }
  const receivedAccount = response.headers.get('X-Ledger-Account');
  if (accountId && receivedAccount && receivedAccount !== accountId) {
    window.dispatchEvent(
      new CustomEvent('ledger:session-expired', {
        detail: 'Your account changed in another tab. Sign in again.',
      }),
    );
    throw new ApiError('Account changed. Please sign in again.', 401);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = describe(payload.detail, response.status);
    if (accountId && response.status === 401)
      window.dispatchEvent(new CustomEvent('ledger:session-expired', { detail: message }));
    throw new ApiError(message, response.status);
  }
  return response;
}
export async function json(path, options) {
  const response = await request(path, options);
  if (response.status === 204) return null;
  return response.json();
}
export async function downloadTransactions(accountId, params = {}) {
  const response = await request(`/api/transactions/export/csv?${new URLSearchParams(params)}`, {
    accountId,
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'ledger-transactions.csv';
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
