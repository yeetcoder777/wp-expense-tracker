import { money, palette, titleCase } from '../lib/format';

export function SpendingChart({ categories, currency }) {
  const total = categories.reduce((sum, item) => sum + Number(item.amount), 0);
  let offset = 0;
  const circumference = 2 * Math.PI * 72;
  return (
    <div className="spending-chart">
      <div className="donut-wrap">
        <svg
          viewBox="0 0 190 190"
          role="img"
          aria-label={
            total
              ? `Spending of ${money(total, currency)} by category`
              : 'No category spending recorded'
          }
        >
          <circle cx="95" cy="95" r="72" fill="none" stroke="var(--line)" strokeWidth="18" />
          {categories
            .filter((item) => Number(item.amount) > 0)
            .map((item, index) => {
              const portion = Number(item.amount) / total;
              const length = Math.max(0, portion * circumference - 4);
              const currentOffset = offset;
              offset += portion * circumference;
              return (
                <circle
                  key={item.category}
                  cx="95"
                  cy="95"
                  r="72"
                  fill="none"
                  stroke={palette[index % palette.length]}
                  strokeWidth="18"
                  strokeDasharray={`${length} ${circumference}`}
                  strokeDashoffset={-currentOffset}
                  transform="rotate(-90 95 95)"
                >
                  <title>
                    {titleCase(item.category)}: {money(item.amount, currency)}
                  </title>
                </circle>
              );
            })}
        </svg>
        <div className="donut-label">
          <span>Total spent</span>
          <strong>{money(total, currency, true)}</strong>
          <small>{categories.length} categories</small>
        </div>
      </div>
      <div className="category-legend">
        {categories.length ? (
          categories.map((item, index) => (
            <div key={item.category}>
              <span
                className="legend-dot"
                style={{ background: palette[index % palette.length] }}
              />
              <span>{titleCase(item.category)}</span>
              <strong>{Math.round((Number(item.amount) / total) * 100)}%</strong>
            </div>
          ))
        ) : (
          <p className="muted">Your spending mix will appear after your first expense.</p>
        )}
      </div>
    </div>
  );
}
export function MovementChart({ current, previous, month }) {
  const max = Math.max(
    Number(current.income),
    Number(current.expenses),
    Number(previous.income),
    Number(previous.expenses),
    1,
  );
  const previousDate = new Date(`${month}-01T12:00:00`);
  previousDate.setMonth(previousDate.getMonth() - 1);
  const labels = [
    previousDate.toLocaleDateString('en-IN', { month: 'short' }),
    new Date(`${month}-01T12:00:00`).toLocaleDateString('en-IN', { month: 'short' }),
  ];
  return (
    <div className="movement-chart">
      <div className="movement-chart-plot">
        <div className="chart-guides">
          <span>{money(max, current.currency, true)}</span>
          <span>{money(max / 2, current.currency, true)}</span>
          <span>0</span>
        </div>
        <div className="bar-groups">
          {[previous, current].map((period, index) => (
            <div className="bar-group" key={index}>
              <div className="paired-bars">
                <div
                  className="chart-bar income-bar"
                  style={{
                    height: `${Math.max((Number(period.income) / max) * 100, Number(period.income) > 0 ? 2 : 0)}%`,
                  }}
                >
                  <span>{money(period.income, current.currency)}</span>
                </div>
                <div
                  className="chart-bar expense-bar"
                  style={{
                    height: `${Math.max((Number(period.expenses) / max) * 100, Number(period.expenses) > 0 ? 2 : 0)}%`,
                  }}
                >
                  <span>{money(period.expenses, current.currency)}</span>
                </div>
              </div>
              <span className="bar-month">{labels[index]}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="chart-key">
        <span>
          <i className="key-income" /> Income
        </span>
        <span>
          <i className="key-expense" /> Spending
        </span>
      </div>
    </div>
  );
}
