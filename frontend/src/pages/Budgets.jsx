import { useState } from 'react';
import { Plus, Pencil, Trash2, Target, ShieldCheck } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLedgerQuery, useLedgerMutation } from '../hooks/useLedger';
import { categories, currentMonth, monthName, money, titleCase } from '../lib/format';
import { CategoryIcon } from '../components/TransactionsTable';
import {
  Button,
  Modal,
  ConfirmModal,
  ErrorState,
  EmptyState,
  Loading,
  useToast,
} from '../components/UI';

function BudgetForm({ budget, currency, onClose }) {
  const save = useLedgerMutation('/api/budgets');
  const notify = useToast();
  return (
    <Modal
      title={budget ? 'Refine your budget' : 'Give your spending a direction'}
      description="Set a monthly limit. Your bot flags spending at 80% and 100%."
      onClose={() => {
        if (!save.isPending) onClose();
      }}
    >
      <form
        className="form-stack"
        onSubmit={async (event) => {
          event.preventDefault();
          const values = Object.fromEntries(new FormData(event.currentTarget));
          try {
            await save.mutateAsync(values);
            notify('Budget saved.');
            onClose();
          } catch {
            /* Error below. */
          }
        }}
      >
        <label>
          Category
          {budget ? (
            <input name="category" value={budget.category} readOnly />
          ) : (
            <select name="category" defaultValue="all">
              <option value="all">Overall spending</option>
              {categories
                .filter((item) => !['salary', 'freelance'].includes(item))
                .map((item) => (
                  <option key={item} value={item}>
                    {titleCase(item)}
                  </option>
                ))}
            </select>
          )}
        </label>
        <div className="form-grid">
          <label>
            Monthly limit
            <input
              type="number"
              min="0.01"
              step="0.01"
              name="amount"
              defaultValue={budget?.amount || ''}
              required
              autoFocus
            />
          </label>
          <label>
            Currency
            <input
              name="currency"
              minLength={3}
              maxLength={10}
              defaultValue={budget?.currency || currency}
              readOnly={Boolean(budget)}
              required
            />
          </label>
        </div>
        {save.error && (
          <p className="inline-error" role="alert">
            {save.error.message}
          </p>
        )}
        <div className="modal-actions">
          <Button variant="secondary" disabled={save.isPending} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={save.isPending}>
            Save budget
          </Button>
        </div>
      </form>
    </Modal>
  );
}
export default function Budgets({ currency }) {
  const { user } = useAuth();
  const notify = useToast();
  const budgets = useLedgerQuery('budgets');
  const [form, setForm] = useState(null);
  const [removing, setRemoving] = useState(null);
  const remove = useLedgerMutation((item) => `/api/budgets/${item.id}`, 'DELETE');
  const rows = (budgets.data || []).filter((item) => item.currency === currency);
  return (
    <>
      <div className="page-toolbar">
        <p className="muted">A little intention makes room for what matters.</p>
        <Button icon={Plus} disabled={user.is_demo} onClick={() => setForm({})}>
          Create budget
        </Button>
      </div>
      <div className="budget-period">
        <span>
          <Target size={17} /> Your plan for {monthName(currentMonth())}
        </span>
        <span>
          {rows.length} {rows.length === 1 ? 'budget' : 'budgets'} in {currency}
        </span>
      </div>
      {budgets.isPending ? (
        <Loading rows={4} />
      ) : budgets.error ? (
        <ErrorState error={budgets.error} retry={budgets.refetch} />
      ) : rows.length ? (
        <div className="budget-grid">
          {rows.map((item) => {
            const percent = (Number(item.spent) / Number(item.amount)) * 100;
            const over = percent >= 100;
            return (
              <article className={`surface budget-card ${over ? 'budget-over' : ''}`} key={item.id}>
                <div className="budget-heading">
                  <CategoryIcon category={item.category === 'all' ? 'other' : item.category} />
                  <div>
                    <h2>
                      {item.category === 'all' ? 'Overall spending' : titleCase(item.category)}
                    </h2>
                    <span>
                      {item.category === 'all'
                        ? 'All your expenses, together'
                        : 'A little structure for the everyday'}
                    </span>
                  </div>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      aria-label={`Edit ${item.category} budget`}
                      disabled={user.is_demo}
                      onClick={() => setForm(item)}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="icon-button danger-icon"
                      aria-label={`Remove ${item.category} budget`}
                      disabled={user.is_demo}
                      onClick={() => setRemoving(item)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
                <div className="budget-numbers">
                  <strong>{money(item.spent, currency)}</strong>
                  <span>of {money(item.amount, currency)} budgeted</span>
                </div>
                <progress max="100" value={Math.min(100, percent)} />
                <div className="budget-bottom">
                  <span>{percent.toFixed(0)}% used</span>
                  <strong>
                    {over
                      ? `${money(Number(item.spent) - Number(item.amount), currency)} over limit`
                      : `${money(item.remaining, currency)} remaining`}
                  </strong>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <section className="surface">
          <EmptyState
            icon={Target}
            title="Make room for your priorities"
            action={
              <Button
                variant="secondary"
                disabled={user.is_demo}
                icon={Plus}
                onClick={() => setForm({})}
              >
                Create your first budget
              </Button>
            }
          >
            Start with an overall limit or a category you want to keep an eye on.
          </EmptyState>
        </section>
      )}
      <div className="quiet-notice">
        <ShieldCheck size={17} />
        <p>
          Budgets follow the current calendar month. Each currency is tracked separately, so your
          limits stay meaningful.
        </p>
      </div>
      {form && (
        <BudgetForm
          budget={form.id ? form : null}
          currency={currency}
          onClose={() => setForm(null)}
        />
      )}
      {removing && (
        <ConfirmModal
          title="Remove this budget?"
          description="The budget and its alert history will be removed. Your transactions stay in your ledger."
          busy={remove.isPending}
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            try {
              await remove.mutateAsync(removing);
              setRemoving(null);
              notify('Budget removed.');
            } catch (error) {
              notify(error.message, true);
            }
          }}
        />
      )}
    </>
  );
}
