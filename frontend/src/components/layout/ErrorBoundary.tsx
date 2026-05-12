import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertOctagon } from 'lucide-react';
import { Button } from '@/components/primitives';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Console for now — production telemetry hook lands at deployment time.
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-[60vh] items-center justify-center p-6">
          <div className="flex max-w-md flex-col items-center gap-3 rounded-xl border border-accent-loss/20 bg-bg-elevated p-8 text-center">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-loss-bg text-accent-loss">
              <AlertOctagon size={18} strokeWidth={1.5} />
            </span>
            <div>
              <h3 className="text-sm font-medium text-text-primary">Something broke on this page.</h3>
              <p className="mt-1 text-xs text-text-tertiary">
                The error was logged. Try reloading; if it keeps happening, the
                Network tab usually has the failing request.
              </p>
            </div>
            <code className="block max-h-32 w-full overflow-auto rounded bg-bg-overlay px-3 py-2 text-left font-mono text-2xs text-text-secondary">
              {this.state.error.message}
            </code>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => this.setState({ error: null })}>
                Try again
              </Button>
              <Button variant="primary" onClick={() => window.location.reload()}>
                Reload page
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
