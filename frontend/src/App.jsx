import { useEffect, useState } from 'react';
import { useIsFetching, useQueryClient } from '@tanstack/react-query';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Target,
  CalendarClock,
  Files,
  Download,
  MessageCircle,
  ChevronDown,
  LogOut,
  Menu,
  X,
  ShieldCheck,
  ArrowUpRight,
  CircleHelp,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from './auth/AuthContext';
import SignIn from './auth/SignIn';
import { useLedgerQuery } from './hooks/useLedger';
import { Brand, Modal, useToast } from './components/UI';
import { currentMonth, monthBounds } from './lib/format';
import { downloadTransactions } from './api/client';
import Overview from './pages/Overview';
import Transactions from './pages/Transactions';
import Budgets from './pages/Budgets';
import Recurring from './pages/Recurring';
import Imports from './pages/Imports';

const navigation = [
  {
    id: 'overview',
    label: 'Overview',
    icon: LayoutDashboard,
    subtitle: 'A considered view of your everyday finances.',
  },
  {
    id: 'transactions',
    label: 'Transactions',
    icon: ArrowLeftRight,
    subtitle: 'Your money’s movements, thoughtfully kept.',
  },
  {
    id: 'budgets',
    label: 'Budgets',
    icon: Target,
    subtitle: 'Spend with intention. Leave room for what matters.',
  },
  {
    id: 'recurring',
    label: 'Recurring',
    icon: CalendarClock,
    subtitle: 'Keep the predictable parts of life in view.',
  },
  {
    id: 'imports',
    label: 'Imports',
    icon: Files,
    subtitle: 'Bring your financial story together.',
  },
];
const pageFromHash = () =>
  navigation.some((item) => item.id === window.location.hash.slice(1))
    ? window.location.hash.slice(1)
    : 'overview';

function Workspace() {
  const { user, signOut } = useAuth();
  const notify = useToast();
  const queryClient = useQueryClient();
  const fetching = useIsFetching({ queryKey: [user.account_id] });
  const [page, setPage] = useState(pageFromHash);
  const [month, setMonth] = useState(currentMonth);
  const [currency, setCurrency] = useState('INR');
  const [menuOpen, setMenuOpen] = useState(false);
  const [recordHelp, setRecordHelp] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 800px)').matches);
  const currencies = useLedgerQuery('currencies');
  const budgetCurrencies = useLedgerQuery('budgets');
  const scheduleCurrencies = useLedgerQuery('recurring');
  useEffect(() => {
    const changed = () => setPage(pageFromHash());
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, []);
  useEffect(() => {
    document.body.style.overflow = menuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [menuOpen]);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 800px)');
    const changed = () => {
      setIsMobile(media.matches);
      if (!media.matches) setMenuOpen(false);
    };
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  useEffect(() => {
    if (menuOpen) document.querySelector('.sidebar .nav-item')?.focus();
  }, [menuOpen]);
  const options = [
    ...new Set([
      'INR',
      ...(currencies.data || []),
      ...(budgetCurrencies.data || []).map((item) => item.currency),
      ...(scheduleCurrencies.data || []).map((item) => item.currency),
    ]),
  ];
  const selectedPage = navigation.find((item) => item.id === page);
  const navigate = (value) => {
    setPage(value);
    setMenuOpen(false);
    window.location.hash = value;
  };
  const leave = async () => {
    setLeaving(true);
    try {
      await signOut();
    } catch (error) {
      notify(error.message, true);
    } finally {
      setLeaving(false);
    }
  };
  const botNumber = (import.meta.env.VITE_WHATSAPP_NUMBER || '').replace(/[^0-9]/g, '');
  return (
    <div className="app-layout">
      {menuOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside
        id="sidebar-navigation"
        inert={isMobile && !menuOpen}
        className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}
      >
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button mobile-close"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="workspace-label">
          <span className="workspace-square">P</span>
          <div>
            <strong>Personal workspace</strong>
            <span>Your everyday finances</span>
          </div>
          <ChevronDown size={13} />
        </div>
        <nav className="main-nav" aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${page === id ? 'nav-active' : ''}`}
              aria-current={page === id ? 'page' : undefined}
              onClick={() => navigate(id)}
            >
              <Icon size={19} strokeWidth={1.5} />
              <span>{label}</span>
              {page === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="whatsapp-note">
            <MessageCircle size={21} strokeWidth={1.3} />
            <h3>
              Life happens.
              <br />
              Just send a message.
            </h3>
            <p>Your WhatsApp entries find their place here.</p>
            <button className="text-link" onClick={() => setRecordHelp(true)}>
              How it works <ArrowUpRight size={14} />
            </button>
          </div>
          <div className="sidebar-privacy">
            <ShieldCheck size={14} />
            <span>Private by design</span>
          </div>
          <div className="account-block">
            <span className="account-avatar">
              {user.is_demo ? 'L' : user.whatsapp_number.slice(-2)}
            </span>
            <div>
              <strong>{user.is_demo ? 'Preview account' : 'Your account'}</strong>
              <span>
                {user.is_demo
                  ? 'Illustrative data'
                  : `WhatsApp · •••• ${user.whatsapp_number.slice(-4)}`}
              </span>
            </div>
            <button
              className="icon-button"
              aria-label={user.is_demo ? 'Leave preview' : 'Sign out'}
              disabled={leaving}
              title={user.is_demo ? 'Leave preview' : 'Sign out'}
              onClick={leave}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="workspace-topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={menuOpen}
              aria-controls="sidebar-navigation"
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span>Workspace</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{selectedPage.label}</strong>
          </div>
          <span className="privacy-indicator">
            <i className="status-dot" />{' '}
            {user.is_demo ? 'Design preview' : 'Your private dashboard'}
          </span>
        </header>
        <main className="workspace">
          {user.is_demo && (
            <div className="preview-banner">
              <span>
                <CircleHelp size={15} /> Read-only preview. These are illustrative records, not your
                account.
              </span>
              <button onClick={leave}>
                Sign in to your ledger <ArrowUpRight size={14} />
              </button>
            </div>
          )}
          <div className="page-heading">
            <div>
              <h1>{selectedPage.label}</h1>
              <p>{selectedPage.subtitle}</p>
            </div>
            <div className="heading-controls">
              <button
                className="icon-button"
                aria-label="Refresh dashboard data"
                title={fetching ? 'Updating dashboard' : 'Refresh dashboard data'}
                disabled={fetching > 0}
                onClick={() => queryClient.invalidateQueries({ queryKey: [user.account_id] })}
              >
                <RefreshCw size={18} />
              </button>
              {['overview', 'transactions'].includes(page) && (
                <label className="period-control">
                  <CalendarClock size={15} />
                  <span className="sr-only">Selected month</span>
                  <input
                    type="month"
                    aria-label="Selected month"
                    value={month}
                    onChange={(event) => {
                      if (event.target.value) setMonth(event.target.value);
                    }}
                  />
                </label>
              )}
              <label className="currency-control">
                <span className="sr-only">Currency</span>
                <select
                  aria-label="Currency"
                  value={currency}
                  onChange={(event) => setCurrency(event.target.value)}
                >
                  {options.map((code) => (
                    <option key={code}>{code}</option>
                  ))}
                </select>
              </label>
              {page === 'overview' && (
                <button
                  className="icon-button export-icon"
                  aria-label="Export selected month as CSV"
                  title="Export selected month"
                  disabled={user.is_demo || exporting}
                  onClick={async () => {
                    setExporting(true);
                    try {
                      await downloadTransactions(user.account_id, {
                        ...monthBounds(month),
                        currency,
                      });
                      notify('Monthly CSV downloaded.');
                    } catch (error) {
                      notify(error.message, true);
                    } finally {
                      setExporting(false);
                    }
                  }}
                >
                  <Download size={18} />
                </button>
              )}
            </div>
          </div>
          <div className="page-content" key={page}>
            {page === 'overview' && (
              <Overview month={month} currency={currency} navigate={navigate} />
            )}
            {page === 'transactions' && (
              <Transactions
                month={month}
                currency={currency}
                onRecord={() => setRecordHelp(true)}
              />
            )}
            {page === 'budgets' && <Budgets currency={currency} />}
            {page === 'recurring' && <Recurring currency={currency} />}
            {page === 'imports' && <Imports />}
          </div>
          <footer className="workspace-footer">
            <span>
              Ledger <span className="footer-dot" /> A little clarity goes a long way.
            </span>
            <span>Amounts shown in {currency}. No currency conversion.</span>
          </footer>
        </main>
      </div>
      {recordHelp && (
        <Modal
          title="As simple as sending a message."
          description="Open your existing chat with the tracker bot on WhatsApp."
          onClose={() => setRecordHelp(false)}
        >
          <div className="message-examples">
            <div>
              <span>You</span>
              <p>I spent ₹250 on coffee</p>
            </div>
            <div>
              <span>Ledger</span>
              <p>Recorded INR 250.00 spent for coffee.</p>
            </div>
          </div>
          <p className="muted">
            Send one transaction per line. Income, expenses and corrections stay linked to your own
            WhatsApp number.
          </p>
          {botNumber && (
            <a
              className="btn btn-primary whatsapp-open"
              href={`https://wa.me/${botNumber}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <MessageCircle size={16} /> Open WhatsApp
            </a>
          )}
        </Modal>
      )}
    </div>
  );
}
export default function App() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="app-loading">
        <Brand />
        <span>Opening your ledger…</span>
      </div>
    );
  return user ? <Workspace key={user.account_id} /> : <SignIn />;
}
