import {
  ArrowDownLeft,
  ArrowUpRight,
  Coffee,
  Home,
  ShoppingBag,
  Car,
  BookOpen,
  HeartPulse,
  BriefcaseBusiness,
  Pencil,
  Trash2,
  Tv,
  CircleDollarSign,
} from 'lucide-react';
import { dateLabel, money, titleCase } from '../lib/format';
import { EmptyState } from './UI';

const categoryIcons = {
  food: Coffee,
  bills: Home,
  shopping: ShoppingBag,
  transport: Car,
  education: BookOpen,
  health: HeartPulse,
  salary: BriefcaseBusiness,
  freelance: BriefcaseBusiness,
  entertainment: Tv,
};
export function CategoryIcon({ category, income = false }) {
  const Icon = categoryIcons[category] || CircleDollarSign;
  return (
    <span
      className={`category-icon category-${category || 'other'} ${income ? 'category-income' : ''}`}
    >
      <Icon size={18} strokeWidth={1.5} />
    </span>
  );
}
export default function TransactionsTable({
  rows,
  compact = false,
  onEdit,
  onDelete,
  disabled = false,
}) {
  if (!rows.length)
    return (
      <EmptyState title="Your story starts with one entry">
        Send an expense to your WhatsApp bot and it will appear here.
      </EmptyState>
    );
  return (
    <div className="table-scroll">
      <table className={`transactions-table ${compact ? 'table-compact' : ''}`}>
        <thead>
          <tr>
            <th>Transaction</th>
            {!compact && <th>Category</th>}
            <th>Date</th>
            <th className="text-right">Amount</th>
            {!compact && (
              <th>
                <span className="sr-only">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <div className="transaction-name">
                  <CategoryIcon
                    category={row.category}
                    income={row.transaction_type === 'income'}
                  />
                  <div>
                    <strong>{row.purpose || row.person || 'Untitled transaction'}</strong>
                    <span>
                      {compact
                        ? titleCase(row.category || 'other')
                        : row.person || `Entry #${row.id}`}
                    </span>
                  </div>
                </div>
              </td>
              {!compact && (
                <td>
                  <span className="category-tag">{titleCase(row.category || 'other')}</span>
                </td>
              )}
              <td className="date-cell">{dateLabel(row.transaction_date)}</td>
              <td
                className={`amount-cell ${row.transaction_type === 'income' ? 'income-text' : ''}`}
              >
                <span className="amount-direction">
                  {row.transaction_type === 'income' ? (
                    <ArrowDownLeft size={13} />
                  ) : (
                    <ArrowUpRight size={13} />
                  )}
                </span>
                {row.transaction_type === 'income' ? '+' : '−'}
                {money(row.amount, row.currency)}
              </td>
              {!compact && (
                <td>
                  <div className="row-actions">
                    <button
                      className="icon-button"
                      title="Edit transaction"
                      aria-label={`Edit ${row.purpose || 'transaction'} #${row.id}`}
                      disabled={disabled}
                      onClick={() => onEdit(row)}
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      className="icon-button danger-icon"
                      title="Delete transaction"
                      aria-label={`Delete transaction #${row.id}`}
                      disabled={disabled}
                      onClick={() => onDelete(row)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
