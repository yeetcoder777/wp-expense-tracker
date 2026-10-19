import { useState } from 'react';
import { Plus, Pause, Play, Trash2, CalendarClock, Bell, Repeat2 } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLedgerQuery, useLedgerMutation } from '../hooks/useLedger';
import { money, dateLabel, categories, titleCase, today } from '../lib/format';
import { CategoryIcon } from '../components/TransactionsTable';
import {
  Button,
  Modal,
  ConfirmModal,
  EmptyState,
  ErrorState,
  Loading,
  useToast,
} from '../components/UI';

function ScheduleForm({ currency, onClose }) {
  const mutation = useLedgerMutation('/api/recurring');
  const notify = useToast();
  return (
    <Modal
      title="One less thing to remember"
      description="Plan a regular payment, income entry, or reminder."
      onClose={() => {
        if (!mutation.isPending) onClose();
      }}
    >
      <form
        className="form-stack"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const values = Object.fromEntries(new FormData(form));
          values.reminder_days = Number(values.reminder_days);
          values.auto_record = form.elements.auto_record.checked;
          try {
            await mutation.mutateAsync(values);
            notify('Schedule added.');
            onClose();
          } catch {
            /* Inline error. */
          }
        }}
      >
        <label>
          Name
          <input name="name" placeholder="Monthly rent" maxLength={150} required autoFocus />
        </label>
        <div className="form-grid">
          <label>
            Type
            <select name="transaction_type">
              <option value="expense">Money out</option>
              <option value="income">Money in</option>
            </select>
          </label>
          <label>
            Repeat
            <select name="interval">
              <option value="monthly">Monthly</option>
              <option value="weekly">Weekly</option>
              <option value="yearly">Yearly</option>
            </select>
          </label>
          <label>
            Amount
            <input name="amount" type="number" min="0.01" step="0.01" required />
          </label>
          <label>
            Currency
            <input name="currency" defaultValue={currency} minLength={3} maxLength={10} required />
          </label>
          <label>
            Category
            <select name="category" defaultValue="bills">
              {categories.map((item) => (
                <option key={item} value={item}>
                  {titleCase(item)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Next due date
            <input type="date" name="next_run_date" defaultValue={today()} required />
          </label>
        </div>
        <label>
          Remind me days before
          <input name="reminder_days" type="number" min="0" max="30" defaultValue="1" required />
        </label>
        <label className="checkbox-label">
          <input type="checkbox" name="auto_record" />
          <span>Automatically record each occurrence</span>
        </label>
        <p className="field-help">
          Schedules run while your tracker is online. WhatsApp reminders depend on the bot’s
          messaging setup.
        </p>
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
            Add schedule
          </Button>
        </div>
      </form>
    </Modal>
  );
}
export default function Recurring({ currency }) {
  const { user } = useAuth();
  const notify = useToast();
  const schedules = useLedgerQuery('recurring');
  const [creating, setCreating] = useState(false);
  const [removing, setRemoving] = useState(null);
  const toggle = useLedgerMutation((item) => `/api/recurring/${item.id}`, 'PATCH');
  const remove = useLedgerMutation((item) => `/api/recurring/${item.id}`, 'DELETE');
  const rows = (schedules.data || []).filter((item) => item.currency === currency);
  return (
    <>
      <div className="page-toolbar">
        <p className="muted">For the things that come around, again and again.</p>
        <Button icon={Plus} disabled={user.is_demo} onClick={() => setCreating(true)}>
          Add schedule
        </Button>
      </div>
      <div className="schedule-intro">
        <span className="schedule-intro-icon">
          <CalendarClock size={28} strokeWidth={1.2} />
        </span>
        <div>
          <h2>A calmer calendar.</h2>
          <p>Rent, subscriptions, salary. Keep the predictable parts of your finances in view.</p>
        </div>
        <span className="quiet-tag">{rows.filter((item) => item.is_active).length} active</span>
      </div>
      <section className="surface">
        {schedules.isPending ? (
          <Loading rows={4} />
        ) : schedules.error ? (
          <ErrorState error={schedules.error} retry={schedules.refetch} />
        ) : rows.length ? (
          <div className="schedule-list">
            {rows.map((item) => (
              <article
                className={`schedule-row ${!item.is_active ? 'schedule-paused' : ''}`}
                key={item.id}
              >
                <CategoryIcon
                  category={item.category}
                  income={item.transaction_type === 'income'}
                />
                <div className="schedule-description">
                  <h3>
                    {item.name} {!item.is_active && <span className="paused-tag">Paused</span>}
                  </h3>
                  <p>
                    {titleCase(item.interval)} <span className="subtle-dot" />{' '}
                    {item.auto_record ? 'Automatically recorded' : 'Reminder only'}
                  </p>
                </div>
                <div className="schedule-due">
                  <span>Next due</span>
                  <strong>{dateLabel(item.next_run_date)}</strong>
                </div>
                <strong className={item.transaction_type === 'income' ? 'income-text' : ''}>
                  {item.transaction_type === 'income' ? '+' : ''}
                  {money(item.amount, currency)}
                </strong>
                <div className="row-actions">
                  <button
                    className="icon-button"
                    disabled={user.is_demo || toggle.isPending}
                    aria-label={`${item.is_active ? 'Pause' : 'Resume'} ${item.name}`}
                    onClick={async () => {
                      try {
                        await toggle.mutateAsync({ id: item.id, is_active: !item.is_active });
                        notify(item.is_active ? 'Schedule paused.' : 'Schedule resumed.');
                      } catch (error) {
                        notify(error.message, true);
                      }
                    }}
                  >
                    {item.is_active ? <Pause size={17} /> : <Play size={17} />}
                  </button>
                  <button
                    className="icon-button danger-icon"
                    disabled={user.is_demo}
                    aria-label={`Delete ${item.name}`}
                    onClick={() => setRemoving(item)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState icon={Repeat2} title="A little planning goes a long way">
            Add a schedule for a bill or income you expect regularly.
          </EmptyState>
        )}
      </section>
      <div className="quiet-notice">
        <Bell size={17} />
        <p>
          Reminders are a heads-up, not a bank payment. Ledger never moves money on your behalf.
        </p>
      </div>
      {creating && <ScheduleForm currency={currency} onClose={() => setCreating(false)} />}
      {removing && (
        <ConfirmModal
          title="Remove this schedule?"
          description="Future occurrences will stop. Previously recorded transactions will remain."
          busy={remove.isPending}
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            try {
              await remove.mutateAsync(removing);
              setRemoving(null);
              notify('Schedule removed.');
            } catch (error) {
              notify(error.message, true);
            }
          }}
        />
      )}
    </>
  );
}
