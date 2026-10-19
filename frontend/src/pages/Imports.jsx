import { useRef, useState } from 'react';
import { FileSpreadsheet, ReceiptText, Upload, Check, ShieldCheck, FileCheck2 } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { json } from '../api/client';
import { useQueryClient } from '@tanstack/react-query';
import { Button, useToast } from '../components/UI';
import { categories, titleCase } from '../lib/format';

function UploadCard({ receipt, onSelect, busy, disabled }) {
  const input = useRef(null);
  const Icon = receipt ? ReceiptText : FileSpreadsheet;
  return (
    <article className="surface upload-card">
      <span className="upload-card-icon">
        <Icon size={27} strokeWidth={1.2} />
      </span>
      <h2>{receipt ? 'A receipt, thoughtfully kept.' : 'Bring the bigger picture.'}</h2>
      <p>
        {receipt
          ? 'Turn a receipt image into entries you can review before adding to your ledger.'
          : 'Import a bank statement and bring your transactions together in one place.'}
      </p>
      <div className="upload-format">
        {receipt ? 'JPG, PNG or WebP' : 'CSV bank statement'}
        <span className="subtle-dot" /> Up to 10 MB
      </div>
      <input
        ref={input}
        type="file"
        className="sr-only"
        accept={receipt ? 'image/jpeg,image/png,image/webp' : '.csv,text/csv'}
        tabIndex={-1}
        aria-label={receipt ? 'Upload receipt image' : 'Upload bank CSV'}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onSelect(file, receipt);
          event.target.value = '';
        }}
      />
      <Button
        variant="secondary"
        icon={Upload}
        busy={busy}
        disabled={disabled}
        onClick={() => input.current.click()}
      >
        {receipt ? 'Choose receipt' : 'Choose statement'}
      </Button>
    </article>
  );
}
export default function Imports() {
  const { user } = useAuth();
  const notify = useToast();
  const client = useQueryClient();
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  async function upload(file, receipt) {
    if (file.size > 10 * 1024 * 1024) {
      setError('Choose a file smaller than 10 MB.');
      return;
    }
    setUploading(receipt ? 'receipt' : 'csv');
    setError('');
    const body = new FormData();
    body.append('file', file);
    try {
      const data = await json(
        receipt ? '/api/imports/receipt/preview' : '/api/imports/csv/preview',
        { method: 'POST', body, accountId: user.account_id },
      );
      setPreview({
        ...data,
        transactions: data.transactions.map((item) => ({
          ...item,
          selected: !item.possible_duplicate,
        })),
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(null);
    }
  }
  function edit(index, name, value) {
    setPreview((old) => ({
      ...old,
      transactions: old.transactions.map((row, i) =>
        i === index ? { ...row, [name]: value } : row,
      ),
    }));
  }
  async function confirm() {
    const selected = preview.transactions.filter((row) => row.selected);
    if (!selected.length) return;
    if (
      selected.some(
        (row) => !row.transaction_date || !row.purpose?.trim() || Number(row.amount) <= 0,
      )
    ) {
      setError('Review the date, description, and positive amount of each selected entry.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await json('/api/imports/confirm', {
        method: 'POST',
        accountId: user.account_id,
        body: {
          transactions: selected.map(({ selected, possible_duplicate, ...row }) => row),
          source_name: preview.source_name,
          skip_possible_duplicates: !selected.some((row) => row.possible_duplicate),
        },
      });
      setPreview(null);
      client.invalidateQueries({ queryKey: [user.account_id] });
      notify(
        `Imported ${result.imported} entries. Skipped ${result.skipped_duplicates} duplicates.`,
      );
      if (result.budget_alerts?.length) setError(result.budget_alerts.join(' '));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }
  const count = preview?.transactions.filter((row) => row.selected).length || 0;
  return (
    <>
      <div className="page-toolbar">
        <p className="muted">A complete picture, without entering every detail.</p>
        <span className="quiet-tag">
          <ShieldCheck size={13} /> Review before saving
        </span>
      </div>
      <div className="upload-grid">
        <UploadCard
          onSelect={upload}
          disabled={user.is_demo || Boolean(uploading) || saving}
          busy={uploading === 'csv'}
        />
        <UploadCard
          receipt
          onSelect={upload}
          disabled={user.is_demo || Boolean(uploading) || saving}
          busy={uploading === 'receipt'}
        />
      </div>
      {error && (
        <p className="inline-error import-message" role="alert">
          {error}
        </p>
      )}
      {preview && (
        <section className="surface import-preview">
          <div className="section-head">
            <div>
              <h2>Make sure everything feels right.</h2>
              <p>
                {preview.source_name} — {preview.transactions.length} entries found. Possible
                duplicates are unselected.
              </p>
            </div>
            <Button icon={Check} disabled={!count || user.is_demo} busy={saving} onClick={confirm}>
              Import {count} selected
            </Button>
          </div>
          {preview.errors?.length > 0 && (
            <div className="import-row-errors">
              {preview.errors.map((item, index) => (
                <p key={index}>
                  Row {item.row}: {item.error}
                </p>
              ))}
            </div>
          )}
          <div className="table-scroll">
            <table className="import-table">
              <thead>
                <tr>
                  <th>
                    <span className="sr-only">Select entry</span>
                  </th>
                  <th>Date</th>
                  <th>Description</th>
                  <th>Category</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Currency</th>
                </tr>
              </thead>
              <tbody>
                {preview.transactions.map((row, index) => (
                  <tr key={index} className={row.possible_duplicate ? 'possible-duplicate' : ''}>
                    <td>
                      <input
                        type="checkbox"
                        checked={row.selected}
                        disabled={saving}
                        onChange={(event) => edit(index, 'selected', event.target.checked)}
                        aria-label={`Include entry ${index + 1}`}
                      />
                    </td>
                    <td>
                      <input
                        type="date"
                        value={row.transaction_date || ''}
                        disabled={saving}
                        onChange={(event) => edit(index, 'transaction_date', event.target.value)}
                        aria-label={`Date for entry ${index + 1}`}
                      />
                    </td>
                    <td>
                      <input
                        value={row.purpose || ''}
                        disabled={saving}
                        onChange={(event) => edit(index, 'purpose', event.target.value)}
                        aria-label={`Description for entry ${index + 1}`}
                      />
                      {row.possible_duplicate && (
                        <small>Possible duplicate — select only to include it</small>
                      )}
                    </td>
                    <td>
                      <select
                        value={row.category || 'other'}
                        disabled={saving}
                        onChange={(event) => edit(index, 'category', event.target.value)}
                        aria-label={`Category for entry ${index + 1}`}
                      >
                        {[...new Set([...categories, row.category].filter(Boolean))].map((item) => (
                          <option key={item} value={item}>
                            {titleCase(item)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={row.transaction_type}
                        disabled={saving}
                        onChange={(event) => edit(index, 'transaction_type', event.target.value)}
                        aria-label={`Type for entry ${index + 1}`}
                      >
                        <option value="expense">Money out</option>
                        <option value="income">Money in</option>
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={row.amount}
                        disabled={saving}
                        onChange={(event) => edit(index, 'amount', event.target.value)}
                        aria-label={`Amount for entry ${index + 1}`}
                      />
                    </td>
                    <td>
                      <input
                        value={row.currency}
                        disabled={saving}
                        maxLength={10}
                        onChange={(event) =>
                          edit(index, 'currency', event.target.value.toUpperCase())
                        }
                        aria-label={`Currency for entry ${index + 1}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="field-help preview-help">
            Only selected rows are saved. Selecting a possible duplicate explicitly includes it.
          </p>
        </section>
      )}
      <div className="import-guidance">
        <FileCheck2 size={20} strokeWidth={1.4} />
        <div>
          <h3>A few details make all the difference.</h3>
          <p>
            Statements should include a date, description and amount. Include a debit/credit or type
            column for income. Receipt reading depends on your bot’s image-reading setup.
          </p>
        </div>
      </div>
    </>
  );
}
