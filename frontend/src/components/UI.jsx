import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { X, Check, AlertCircle, LoaderCircle, ArrowUpRight } from 'lucide-react';

export function Button({
  children,
  icon: Icon,
  variant = 'primary',
  busy = false,
  disabled = false,
  type = 'button',
  className = '',
  ...props
}) {
  return (
    <button
      {...props}
      type={type}
      className={`btn btn-${variant} ${className}`}
      disabled={busy || disabled}
    >
      {busy ? (
        <LoaderCircle size={16} className="spin" />
      ) : (
        Icon && <Icon size={16} strokeWidth={1.7} />
      )}
      {children}
    </button>
  );
}
export function Brand({ light = false, compact = false }) {
  return (
    <div className={`brand ${light ? 'brand-light' : ''}`}>
      <span className="brand-symbol" aria-hidden="true">
        <i />
        <i />
      </span>
      {!compact && (
        <span>
          ledger<span className="brand-period">.</span>
        </span>
      )}
    </div>
  );
}
export function EmptyState({ icon: Icon = ArrowUpRight, title, children, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={23} strokeWidth={1.3} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function ErrorState({ error, retry }) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={19} />
      <div>
        <strong>We couldn’t load this view</strong>
        <p>{error?.message || 'Please try again.'}</p>
      </div>
      {retry && (
        <Button variant="quiet" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}
export function Loading({ rows = 3 }) {
  return (
    <div className="skeleton-stack" role="status" aria-label="Loading your records">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" />
      ))}
    </div>
  );
}
export function Modal({ title, description, children, onClose, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? 'modal-wide' : ''}`}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const rect = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
      aria-labelledby="modal-heading"
    >
      <header className="modal-header">
        <div>
          <h2 id="modal-heading">{title}</h2>
          {description && <p>{description}</p>}
        </div>
        <button className="icon-button" aria-label="Close dialog" onClick={onClose}>
          <X size={20} />
        </button>
      </header>
      {children}
    </dialog>
  );
}
const ToastContext = createContext(null);
export function ToastProvider({ children }) {
  const [notice, setNotice] = useState(null);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(null), 4500);
    return () => clearTimeout(timer);
  }, [notice]);
  return (
    <ToastContext.Provider
      value={(message, error = false) => setNotice({ message, error, key: Date.now() })}
    >
      {children}
      <div
        className={`toast ${notice ? 'visible' : ''} ${notice?.error ? 'toast-error' : ''}`}
        role="status"
        aria-live="polite"
      >
        {notice && (
          <>
            {notice.error ? <AlertCircle size={18} /> : <Check size={18} />}
            <span>{notice.message}</span>
            <button aria-label="Dismiss notification" onClick={() => setNotice(null)}>
              <X size={15} />
            </button>
          </>
        )}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
export function ConfirmModal({ title, description, busy, onConfirm, onClose }) {
  return (
    <Modal
      title={title}
      description={description}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="modal-actions">
        <Button variant="secondary" disabled={busy} onClick={onClose}>
          Keep it
        </Button>
        <Button variant="danger" busy={busy} onClick={onConfirm}>
          Confirm
        </Button>
      </div>
    </Modal>
  );
}
