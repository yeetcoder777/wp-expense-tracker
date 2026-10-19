import { currentMonth } from '../lib/format';
export function demoTransactions(month = currentMonth()) {
  return [
    [9, 'expense', '4850.00', 'food', 'Weekly groceries', 'Fresh Market', 18],
    [8, 'expense', '780.00', 'food', 'Coffee & conversation', 'Third Wave Coffee', 17],
    [7, 'income', '15000.00', 'freelance', 'Design consultation', 'Freelance', 16],
    [6, 'expense', '1980.00', 'food', 'Dinner with friends', 'The Table', 15],
    [5, 'expense', '860.00', 'transport', 'Getting around', 'Uber', 12],
    [4, 'expense', '1490.00', 'education', 'A little new perspective', 'Books & beyond', 10],
    [3, 'expense', '2520.00', 'bills', 'Monthly subscriptions', 'Subscriptions', 5],
    [2, 'expense', '24000.00', 'bills', 'Home, for the month', 'Rent', 3],
    [1, 'income', '110000.00', 'salary', 'Monthly salary', 'Salary', 1],
  ].map(([id, transaction_type, amount, category, purpose, person, day]) => ({
    id,
    transaction_type,
    amount,
    category,
    purpose,
    person,
    currency: 'INR',
    transaction_date: `${month}-${String(day).padStart(2, '0')}`,
  }));
}
export function demoReport(month = currentMonth()) {
  return {
    current: {
      income: '125000.00',
      expenses: '36480.00',
      net: '88520.00',
      savings_rate: '70.82',
      currency: 'INR',
      categories: [
        { category: 'bills', amount: '26520' },
        { category: 'food', amount: '7610' },
        { category: 'education', amount: '1490' },
        { category: 'transport', amount: '860' },
      ],
      largest_expenses: demoTransactions(month)
        .filter((row) => row.transaction_type === 'expense')
        .sort((a, b) => Number(b.amount) - Number(a.amount))
        .slice(0, 5),
    },
    previous: {
      income: '100000',
      expenses: '42100',
      net: '57900',
      savings_rate: '57.90',
      currency: 'INR',
    },
    expense_change: '-5620',
    expense_change_percent: '-13.35',
  };
}
export const demoBudgets = [
  {
    id: 1,
    category: 'all',
    amount: '55000',
    spent: '36480',
    remaining: '18520',
    currency: 'INR',
    percent_used: 66.33,
  },
  {
    id: 2,
    category: 'food',
    amount: '12000',
    spent: '7610',
    remaining: '4390',
    currency: 'INR',
    percent_used: 63.42,
  },
  {
    id: 3,
    category: 'transport',
    amount: '4000',
    spent: '860',
    remaining: '3140',
    currency: 'INR',
    percent_used: 21.5,
  },
];
export const demoRecurring = [
  {
    id: 1,
    name: 'Monthly rent',
    transaction_type: 'expense',
    amount: '24000',
    currency: 'INR',
    category: 'bills',
    interval: 'monthly',
    next_run_date: `${currentMonth()}-28`,
    reminder_days: 2,
    auto_record: false,
    is_active: true,
  },
  {
    id: 2,
    name: 'Subscriptions',
    transaction_type: 'expense',
    amount: '2520',
    currency: 'INR',
    category: 'bills',
    interval: 'monthly',
    next_run_date: `${currentMonth()}-25`,
    reminder_days: 1,
    auto_record: false,
    is_active: true,
  },
];
