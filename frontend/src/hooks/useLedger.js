import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../auth/AuthContext';
import { json } from '../api/client';
import { demoTransactions, demoReport, demoBudgets, demoRecurring } from '../data/demo';

export function useLedgerQuery(name, params = {}, { enabled = true } = {}) {
  const { user } = useAuth();
  return useQuery({
    queryKey: [user?.account_id, name, params],
    enabled: Boolean(user) && enabled,
    queryFn: async ({ signal }) => {
      if (user.is_demo) {
        if (name === 'currencies') return ['INR'];
        if (name === 'monthly') return demoReport(params.month_key);
        if (name === 'budgets') return demoBudgets;
        if (name === 'recurring') return demoRecurring;
        if (name === 'transactions') {
          const rows = demoTransactions(params.start_date?.slice(0, 7));
          return rows
            .filter(
              (row) =>
                (!params.transaction_type || row.transaction_type === params.transaction_type) &&
                (!params.category || row.category === params.category),
            )
            .slice(
              Number(params.offset || 0),
              Number(params.offset || 0) + Number(params.limit || 100),
            );
        }
        return null;
      }
      const { month_key, ...query } = params;
      const path =
        name === 'monthly'
          ? 'reports/monthly'
          : name === 'currencies'
            ? 'transactions/currencies'
            : name;
      return json(
        `/api/${path}?${new URLSearchParams(Object.entries(query).filter(([, value]) => value !== '' && value != null))}`,
        { accountId: user.account_id, signal },
      );
    },
    retry: false,
  });
}
export function useLedgerMutation(path, method = 'POST') {
  const { user } = useAuth();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body) => {
      if (user.is_demo) throw new Error('Preview is read-only. Sign in to manage your records.');
      return json(typeof path === 'function' ? path(body) : path, {
        method,
        body: method === 'DELETE' ? undefined : body,
        accountId: user.account_id,
      });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: [user.account_id] }),
  });
}
