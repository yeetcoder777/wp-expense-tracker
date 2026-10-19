import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { json } from '../api/client';

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const queryClient = useQueryClient();
  const accept = useCallback(
    (account) => {
      queryClient.cancelQueries();
      queryClient.clear();
      setMessage('');
      setUser(account);
    },
    [queryClient],
  );
  useEffect(() => {
    const controller = new AbortController();
    json('/api/auth/me', { signal: controller.signal })
      .then(accept)
      .catch((error) => {
        if (!controller.signal.aborted && error.status !== 401) setMessage(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [accept]);
  useEffect(() => {
    function expired(event) {
      queryClient.cancelQueries();
      queryClient.clear();
      setUser(null);
      setMessage(event.detail || 'Please sign in again.');
    }
    window.addEventListener('ledger:session-expired', expired);
    return () => window.removeEventListener('ledger:session-expired', expired);
  }, [queryClient]);
  const signOut = async () => {
    if (!user?.is_demo) await json('/api/auth/logout', { method: 'POST', body: {} });
    queryClient.cancelQueries();
    queryClient.clear();
    setUser(null);
    setMessage('');
  };
  const preview = () =>
    accept({
      account_id: 'illustrative-preview',
      whatsapp_number: 'Preview account',
      is_demo: true,
    });
  return (
    <AuthContext.Provider value={{ user, loading, message, accept, signOut, preview }}>
      {children}
    </AuthContext.Provider>
  );
}
export const useAuth = () => useContext(AuthContext);
