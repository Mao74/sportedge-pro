import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { TrendingUp } from 'lucide-react';
import { Button, Input } from '@/components/primitives';
import { ApiError, api } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface UserMe {
  id: string;
  email: string;
  created_at: string;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isAuthed = useAuthStore((s) => s.isAuthenticated());
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? '/';

  if (isAuthed) {
    return <Navigate to={from} replace />;
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const tokens = await api.post<TokenPair>('/auth/login', { email, password });
      setTokens(tokens.access_token, tokens.refresh_token);
      const me = await api.get<UserMe>('/auth/me');
      setUser({ id: me.id, email: me.email });
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.problem.title);
      } else {
        setError('Login failed. Try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-base p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-brand-bg text-accent-brand">
            <TrendingUp size={20} strokeWidth={2} />
          </div>
          <div>
            <div className="text-sm font-medium text-text-primary">SportEdge Pro</div>
            <div className="text-xs text-text-tertiary">Sign in to continue</div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="rounded-xl border border-border-subtle bg-bg-elevated p-6">
          <div className="space-y-4">
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error ? (
              <div className="rounded-lg border border-accent-loss/30 bg-accent-loss-bg px-3 py-2 text-xs text-accent-loss">
                {error}
              </div>
            ) : null}
            <Button
              type="submit"
              variant="primary"
              size="xl"
              className="w-full"
              loading={submitting}
            >
              Sign in
            </Button>
          </div>
        </form>

        <p className="mt-6 text-center text-xs text-text-tertiary">
          Single-user journal · self-hosted
        </p>
      </div>
    </div>
  );
}
