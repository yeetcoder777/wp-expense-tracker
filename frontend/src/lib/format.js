export function money(value, currency = 'INR', compact = false) {
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      maximumFractionDigits: compact ? 0 : 2,
      minimumFractionDigits: compact ? 0 : 2,
    }).format(Number(value || 0));
  } catch {
    return `${currency} ${Number(value || 0).toLocaleString('en-IN')}`;
  }
}
export const today = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
export const currentMonth = () => today().slice(0, 7);
export const monthName = (month) =>
  new Date(`${month}-01T12:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
export const dateLabel = (date) =>
  date
    ? new Date(`${date.slice(0, 10)}T12:00:00`).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
      })
    : 'No date';
export const titleCase = (value = '') =>
  value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
export const categories = [
  'food',
  'transport',
  'shopping',
  'bills',
  'entertainment',
  'health',
  'education',
  'salary',
  'freelance',
  'other',
];
export const palette = ['#cfb980', '#91b8cc', '#93c5ab', '#c9a1b6', '#b2abd4', '#dfa58f', '#aec3c4', '#d0c7b4'];
export function monthBounds(month) {
  const [year, part] = month.split('-').map(Number);
  return { start_date: `${month}-01`, end_date: `${month}-${new Date(year, part, 0).getDate()}` };
}
