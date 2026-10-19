import { useState } from 'react';
import {
  ArrowDownLeft,
  ArrowUpRight,
  ArrowRight,
  SlidersHorizontal,
  Wallet,
  ShieldCheck,
  CalendarDays,
  ChevronRight,
} from 'lucide-react';
import { useLedgerQuery } from '../hooks/useLedger';
import { useAuth } from '../auth/AuthContext';
import { money, monthBounds, monthName, titleCase, dateLabel } from '../lib/format';
import { Button, ErrorState, Loading, Modal } from '../components/UI';
import TransactionsTable from '../components/TransactionsTable';
import { MovementChart, SpendingChart } from '../components/Charts';

function RangeReport({ currency, onClose }) {
  const { user } = useAuth();
  const [range, setRange] = useState(null);
  const report = useLedgerQuery('reports/range', range || {}, {
    enabled: Boolean(range) && !user.is_demo,
  });
  return (
    <Modal
      title="A different perspective"
      description="Choose any period to see income, spending, and savings."
      onClose={onClose}
    >
      <form
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          const values = Object.fromEntries(new FormData(event.currentTarget));
          setRange({ ...values, currency });
        }}
      >
        <div className="form-grid">
          <label>
            From
            <input type="date" name="start_date" required />
          </label>
          <label>
            To
            <input type="date" name="end_date" required />
          </label>
        </div>
        <Button type="submit" disabled={user.is_demo} busy={report.isFetching}>
          View report
        </Button>
      </form>
      {report.error && <ErrorState error={report.error} />}
      {report.data && (
        <div className="range-summary">
          <div>
            <span>Income</span>
            <strong>{money(report.data.income, currency)}</strong>
          </div>
          <div>
            <span>Spending</span>
            <strong>{money(report.data.expenses, currency)}</strong>
          </div>
          <div>
            <span>Net</span>
            <strong>{money(report.data.net, currency)}</strong>
          </div>
          <div>
            <span>Savings rate</span>
            <strong>{Number(report.data.savings_rate).toFixed(1)}%</strong>
          </div>
        </div>
      )}
      {user.is_demo && <p className="field-help">Sign in to explore your own date ranges.</p>}
    </Modal>
  );
}
export default function Overview({ month, currency, navigate }) {
  const [customRange, setCustomRange] = useState(false);
  const [activityView, setActivityView] = useState('recent');
  const [year, part] = month.split('-').map(Number);
  const report = useLedgerQuery('monthly', { year, month: part, month_key: month, currency });
  const recent = useLedgerQuery('transactions', { ...monthBounds(month), currency, limit: 6 });
  const budgets = useLedgerQuery('budgets');
  const recurring = useLedgerQuery('recurring');
  if (report.isPending) return <Loading rows={5} />;
  if (report.error) return <ErrorState error={report.error} retry={report.refetch} />;
  const { current, previous, expense_change_percent: change } = report.data;
  const upcoming = (recurring.data || [])
    .filter((item) => item.is_active && item.currency === currency)
    .sort((a, b) => a.next_run_date.localeCompare(b.next_run_date))
    .slice(0, 2);
  const activeBudgets = (budgets.data || [])
    .filter((item) => item.currency === currency)
    .slice(0, 3);
  return (
    <>
      <div className="overview-intro">
        <p>A little perspective on {monthName(month).split(' ')[0]}.</p>
        <button className="text-link" onClick={() => setCustomRange(true)}>
          <SlidersHorizontal size={14} /> Custom date range
        </button>
      </div>
      <section className="summary-grid" aria-label="Monthly financial summary">
        <article className="net-card">
          <div className="net-card-top">
            <span>Net this month</span>
            <Wallet size={21} strokeWidth={1.2} />
          </div>
          <strong className="net-amount">{money(current.net, currency)}</strong>
          <div className="net-card-footer">
            <span>Income less spending</span>
            <span className="net-seal">
              <ShieldCheck size={13} /> Your personal ledger
            </span>
          </div>
        </article>
        <article className="metric-card">
          <span className="metric-icon income-icon">
            <ArrowDownLeft size={20} strokeWidth={1.5} />
          </span>
          <span className="metric-label">Money in</span>
          <strong>{money(current.income, currency)}</strong>
          <span className="metric-foot">Income recorded this month</span>
        </article>
        <article className="metric-card">
          <span className="metric-icon expense-icon">
            <ArrowUpRight size={20} strokeWidth={1.5} />
          </span>
          <span className="metric-label">Money out</span>
          <strong>{money(current.expenses, currency)}</strong>
          <span
            className={`metric-foot ${change !== null && Number(change) <= 0 ? 'income-text' : ''}`}
          >
            {change === null
              ? 'No previous spending to compare'
              : `${Math.abs(Number(change)).toFixed(1)}% ${Number(change) <= 0 ? 'less' : 'more'} than last month`}
          </span>
        </article>
      </section>
      <div className="savings-note">
        <span>
          <i className="status-dot" />{' '}
          {Number(current.income) > 0 ? (
            <>
              <strong>{Number(current.savings_rate).toFixed(1)}%</strong> of recorded income remains
              after spending.
            </>
          ) : (
            'Record income to see your savings rate.'
          )}
        </span>
        <span>One currency. A clearer picture.</span>
      </div>
      <div className="analysis-grid">
        <section className="surface">
          <div className="section-head">
            <div>
              <h2>Monthly movement</h2>
              <p>Income and spending, side by side.</p>
            </div>
            <span className="quiet-tag">Two-month view</span>
          </div>
          <MovementChart current={current} previous={previous} month={month} />
        </section>
        <section className="surface">
          <div className="section-head">
            <div>
              <h2>The spending mix</h2>
              <p>Where this month’s money went.</p>
            </div>
          </div>
          <SpendingChart categories={current.categories} currency={currency} />
        </section>
      </div>
      <div className="activity-grid">
        <section className="surface activity-surface">
          <div className="section-head">
            <div>
              <h2>{activityView === 'recent' ? 'Recent activity' : 'Largest expenses'}</h2>
              <p>
                {activityView === 'recent'
                  ? 'The small things that add up.'
                  : 'Your five biggest expenses this month.'}
              </p>
            </div>
            <div className="activity-controls">
              <div className="view-switch" role="group" aria-label="Activity view">
                <button
                  aria-pressed={activityView === 'recent'}
                  onClick={() => setActivityView('recent')}
                >
                  Recent
                </button>
                <button
                  aria-pressed={activityView === 'largest'}
                  onClick={() => setActivityView('largest')}
                >
                  Largest
                </button>
              </div>
              <button className="text-link" onClick={() => navigate('transactions')}>
                View all <ArrowRight size={14} />
              </button>
            </div>
          </div>
          {activityView === 'largest' ? (
            <TransactionsTable rows={current.largest_expenses} compact />
          ) : recent.isPending ? (
            <Loading />
          ) : recent.error ? (
            <ErrorState error={recent.error} retry={recent.refetch} />
          ) : (
            <TransactionsTable rows={recent.data} compact />
          )}
        </section>
        <div className="aside-stack">
          <section className="surface">
            <div className="section-head">
              <div>
                <h2>A little room to spend</h2>
                <p>Current-month budgets.</p>
              </div>
            </div>
            {budgets.error ? (
              <ErrorState error={budgets.error} retry={budgets.refetch} />
            ) : activeBudgets.length ? (
              <div className="mini-budgets">
                {activeBudgets.map((item) => (
                  <div key={item.id}>
                    <div>
                      <strong>
                        {item.category === 'all' ? 'Overall budget' : titleCase(item.category)}
                      </strong>
                      <span>{Math.round((Number(item.spent) / Number(item.amount)) * 100)}%</span>
                    </div>
                    <progress max="100" value={Math.min(100, Number(item.percent_used))} />
                    <small>{money(item.remaining, currency, true)} remaining</small>
                  </div>
                ))}
              </div>
            ) : (
              <p className="aside-empty">A budget gives your spending a little direction.</p>
            )}
            <button className="aside-link" onClick={() => navigate('budgets')}>
              Manage budgets <ChevronRight size={15} />
            </button>
          </section>
          <section className="upcoming-panel">
            <div className="section-head">
              <h2>On the horizon</h2>
              <CalendarDays size={18} strokeWidth={1.5} />
            </div>
            {recurring.error ? (
              <p className="muted">Schedules couldn’t be loaded.</p>
            ) : upcoming.length ? (
              upcoming.map((item) => (
                <div className="upcoming-row" key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <span>{dateLabel(item.next_run_date)}</span>
                  </div>
                  <strong>{money(item.amount, currency, true)}</strong>
                </div>
              ))
            ) : (
              <p className="aside-empty">No active schedules in this currency.</p>
            )}
            <button className="aside-link" onClick={() => navigate('recurring')}>
              View schedules <ChevronRight size={15} />
            </button>
          </section>
        </div>
      </div>
      {customRange && <RangeReport currency={currency} onClose={() => setCustomRange(false)} />}
    </>
  );
}
