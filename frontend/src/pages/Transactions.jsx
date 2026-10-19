import { useEffect, useMemo, useState } from 'react';
import {
  Search,
  Download,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  MessageCircle,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLedgerQuery, useLedgerMutation } from '../hooks/useLedger';
import { downloadTransactions } from '../api/client';
import { categories, titleCase, monthBounds } from '../lib/format';
import { Button, ConfirmModal, Modal, ErrorState, Loading, useToast } from '../components/UI';
import TransactionsTable from '../components/TransactionsTable';

function EditTransaction({ row, onClose }) {
  const mutation = useLedgerMutation(`/api/transactions/${row.id}`, 'PATCH');
  const notify = useToast();
  async function save(event) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await mutation.mutateAsync(body);
      notify('Transaction updated.');
      onClose();
    } catch {
      /* Inline API error below. */
    }
  }
  return (
    <Modal
      title="A small correction"
      description={`Update transaction #${row.id}.`}
      onClose={() => {
        if (!mutation.isPending) onClose();
      }}
    >
      <form onSubmit={save} className="form-stack">
        <label>
          Description
          <input
            name="purpose"
            defaultValue={row.purpose || ''}
            maxLength={500}
            required
            autoFocus
          />
        </label>
        <div className="form-grid">
          <label>
            Amount
            <input
              name="amount"
              type="number"
              min="0.01"
              step="0.01"
              defaultValue={row.amount}
              required
            />
          </label>
          <label>
            Date
            <input
              name="transaction_date"
              type="date"
              defaultValue={row.transaction_date || ''}
              required
            />
          </label>
        </div>
        <label>
          Category
          <select name="category" defaultValue={row.category || 'other'}>
            {categories.map((category) => (
              <option key={category} value={category}>
                {titleCase(category)}
              </option>
            ))}
          </select>
        </label>
        {mutation.error && (
          <p className="inline-error" role="alert">
            {mutation.error.message}
          </p>
        )}
        <div className="modal-actions">
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" busy={mutation.isPending}>
            Save changes
          </Button>
        </div>
      </form>
    </Modal>
  );
}
export default function Transactions({ month, currency, onRecord }) {
  const { user } = useAuth();
  const notify = useToast();
  const [filters, setFilters] = useState({
    ...monthBounds(month),
    transaction_type: '',
    category: '',
  });
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [exporting, setExporting] = useState(false);
  useEffect(() => {
    setFilters((old) => ({ ...old, ...monthBounds(month) }));
    setOffset(0);
  }, [month]);
  useEffect(() => setOffset(0), [currency]);
  const transactions = useLedgerQuery('transactions', { ...filters, currency, limit: 25, offset });
  const remove = useLedgerMutation((row) => `/api/transactions/${row.id}`, 'DELETE');
  const undo = useLedgerMutation('/api/transactions/undo');
  const rows = useMemo(
    () =>
      (transactions.data || []).filter((row) =>
        `${row.purpose || ''} ${row.person || ''} ${row.category || ''}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ),
    [transactions.data, search],
  );
  function filter(name, value) {
    setFilters((old) => ({ ...old, [name]: value }));
    setOffset(0);
  }
  async function confirm() {
    try {
      if (confirmation.undo) await undo.mutateAsync({});
      else await remove.mutateAsync(confirmation.row);
      setConfirmation(null);
      notify('Transaction removed.');
    } catch (error) {
      notify(error.message, true);
    }
  }
  return (
    <>
      <div className="page-toolbar">
        <p className="muted">Every entry, with room to make it right.</p>
        <div className="toolbar-actions">
          <Button
            variant="secondary"
            icon={RotateCcw}
            disabled={user.is_demo}
            onClick={() => setConfirmation({ undo: true })}
          >
            Undo latest
          </Button>
          <Button icon={MessageCircle} onClick={onRecord}>
            Record on WhatsApp
          </Button>
        </div>
      </div>
      <section className="surface transactions-surface">
        <div className="transaction-controls">
          <div className="search-box">
            <Search size={17} />
            <input
              aria-label="Search transactions on this page"
              placeholder="Search this page"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Button
            variant="quiet"
            icon={Download}
            busy={exporting}
            disabled={user.is_demo}
            onClick={async () => {
              setExporting(true);
              try {
                await downloadTransactions(user.account_id, {
                  start_date: filters.start_date,
                  end_date: filters.end_date,
                  currency,
                });
                notify('Date-range CSV downloaded.');
              } catch (error) {
                notify(error.message, true);
              } finally {
                setExporting(false);
              }
            }}
          >
            Export date range
          </Button>
        </div>
        <div className="filter-strip">
          <label>
            From
            <input
              type="date"
              value={filters.start_date}
              onChange={(event) => filter('start_date', event.target.value)}
            />
          </label>
          <label>
            To
            <input
              type="date"
              value={filters.end_date}
              onChange={(event) => filter('end_date', event.target.value)}
            />
          </label>
          <label>
            Type
            <select
              value={filters.transaction_type}
              onChange={(event) => filter('transaction_type', event.target.value)}
            >
              <option value="">All types</option>
              <option value="expense">Money out</option>
              <option value="income">Money in</option>
            </select>
          </label>
          <label>
            Category
            <select
              value={filters.category}
              onChange={(event) => filter('category', event.target.value)}
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option value={category} key={category}>
                  {titleCase(category)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {transactions.isPending ? (
          <Loading rows={5} />
        ) : transactions.error ? (
          <ErrorState error={transactions.error} retry={transactions.refetch} />
        ) : (
          <TransactionsTable
            rows={rows}
            onEdit={setEditing}
            onDelete={(row) => setConfirmation({ row })}
            disabled={user.is_demo}
          />
        )}
        <footer className="table-footer">
          <span>
            {transactions.data?.length
              ? `Entries ${offset + 1}–${offset + transactions.data.length}`
              : 'No entries in this view'}
            <small>CSV includes the selected dates and currency.</small>
          </span>
          <div>
            <Button
              variant="quiet"
              icon={ChevronLeft}
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 25))}
            >
              Previous
            </Button>
            <Button
              variant="quiet"
              disabled={(transactions.data?.length || 0) < 25}
              onClick={() => setOffset(offset + 25)}
            >
              Next <ChevronRight size={15} />
            </Button>
          </div>
        </footer>
      </section>
      {editing && (
        <EditTransaction key={editing.id} row={editing} onClose={() => setEditing(null)} />
      )}
      {confirmation && (
        <ConfirmModal
          title={confirmation.undo ? 'Undo the latest entry?' : 'Remove this transaction?'}
          description="This permanently removes the entry from your ledger. It cannot be restored from the dashboard."
          busy={remove.isPending || undo.isPending}
          onConfirm={confirm}
          onClose={() => setConfirmation(null)}
        />
      )}
    </>
  );
}
