import { useEffect, useState } from 'react';
import {
  ArrowRight,
  Check,
  Copy,
  LockKeyhole,
  MessageCircle,
  ShieldCheck,
  LoaderCircle,
} from 'lucide-react';
import { useAuth } from './AuthContext';
import { json } from '../api/client';
import { Brand, Button } from '../components/UI';

export default function SignIn() {
  const { accept, preview, message } = useAuth();
  const [phone, setPhone] = useState('');
  const [challenge, setChallenge] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!challenge) return;
    const controller = new AbortController();
    let timeout;
    const tick = () =>
      setSeconds(Math.max(0, Math.ceil((Date.parse(challenge.expires_at) - Date.now()) / 1000)));
    tick();
    const clock = setInterval(tick, 1000);
    async function poll() {
      if (Date.now() >= Date.parse(challenge.expires_at)) {
        setChallenge(null);
        setError('This code expired. Request a new one to continue.');
        return;
      }
      try {
        const data = await json('/api/auth/login/complete', {
          method: 'POST',
          signal: controller.signal,
          body: { request_id: challenge.request_id, poll_secret: challenge.poll_secret },
        });
        if (controller.signal.aborted) return;
        if (data.status === 'authenticated') {
          accept(data.account);
          return;
        }
        timeout = setTimeout(poll, 3000);
      } catch (err) {
        if (!controller.signal.aborted) {
          setChallenge(null);
          setError(err.message);
        }
      }
    }
    timeout = setTimeout(poll, 1500);
    return () => {
      controller.abort();
      clearTimeout(timeout);
      clearInterval(clock);
    };
  }, [challenge, accept]);
  async function start(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const data = await json('/api/auth/login/start', {
        method: 'POST',
        body: { phone: phone.replace(/[\s()-]/g, '') },
      });
      setChallenge(data);
      setCopied(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="signin-page">
      <section className="signin-story">
        <Brand light />
        <div className="signin-story-content">
          <span className="small-caption">
            <span className="tiny-rule" /> A little clarity, every day
          </span>
          <h1>
            Your money.
            <br />A quieter mind.
          </h1>
          <p>
            Every small purchase. Every bigger plan.
            <br />
            One considered place to see it all.
          </p>
          <div className="signin-illustration" aria-hidden="true">
            <div className="illustration-orbit orbit-one" />
            <div className="illustration-orbit orbit-two" />
            <div className="illustration-card">
              <span>Made for the everyday</span>
              <span className="illustration-line" />
              <div className="illustration-bars">
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
                <i />
              </div>
              <span className="illustration-monogram">L.</span>
            </div>
            <span className="illustration-dot" />
          </div>
        </div>
        <p className="signin-footer">Personal finance, thoughtfully kept.</p>
      </section>
      <section className="signin-content">
        <div className="signin-mobile-brand">
          <Brand />
        </div>
        <div className="signin-form-wrap">
          <span className="signin-lock">
            <LockKeyhole size={21} strokeWidth={1.4} />
          </span>
          <h2>{challenge ? 'One message. You’re in.' : 'Welcome to your ledger.'}</h2>
          <p className="signin-intro">
            {challenge
              ? 'Send the command below from your WhatsApp number. We’ll open your dashboard right here.'
              : 'Your own space for a clearer picture of your finances. Sign in securely with WhatsApp.'}
          </p>
          {!challenge ? (
            <form onSubmit={start} className="form-stack">
              <label htmlFor="phone">Your WhatsApp number</label>
              <div className="phone-input">
                <MessageCircle size={19} />
                <input
                  id="phone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="+91 98765 43210"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  maxLength={24}
                  required
                  autoFocus
                />
              </div>
              <p className="field-help">
                Include your country code. Use the number you track expenses with.
              </p>
              <Button type="submit" busy={busy} className="full-width">
                Continue with WhatsApp <ArrowRight size={16} />
              </Button>
            </form>
          ) : (
            <div className="login-approval">
              <div className="login-code">
                <code>{challenge.command}</code>
                <button
                  className="icon-button"
                  aria-label="Copy login command"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(challenge.command);
                      setCopied(true);
                    } catch {
                      setError('Select and copy the command above, then send it to the bot.');
                    }
                  }}
                >
                  {copied ? <Check size={17} /> : <Copy size={17} />}
                </button>
              </div>
              <a
                className="btn btn-primary full-width"
                href={challenge.whatsapp_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <MessageCircle size={17} /> Open WhatsApp
              </a>
              <div className="approval-status" role="status">
                <LoaderCircle size={15} className="spin" />
                <span>Waiting for your message</span>
                <span>
                  {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}
                </span>
              </div>
              <button
                className="text-link"
                onClick={() => {
                  setChallenge(null);
                  setError('');
                }}
              >
                Use another number or request a new code
              </button>
            </div>
          )}
          {(error || message) && (
            <p className="inline-error" role="alert">
              {error || message}
            </p>
          )}
          <div className="signin-assurance">
            <ShieldCheck size={16} />
            <p>
              {challenge
                ? 'Only approve a code you requested. Return to this same browser after sending it. Sandbox users must join the bot first.'
                : 'No passwords to remember. Your records are private to your verified number.'}
            </p>
          </div>
          <div className="signin-preview">
            <span>Just looking around?</span>
            <button className="text-link" onClick={preview}>
              Explore a preview <ArrowRight size={14} />
            </button>
          </div>
        </div>
        <footer className="signin-legal">
          <span>Ledger</span>
          <span>Built around your privacy.</span>
        </footer>
      </section>
    </main>
  );
}
