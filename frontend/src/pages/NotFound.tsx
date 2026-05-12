import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Button } from '@/components/primitives';

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-brand-bg text-accent-brand">
        <Compass size={20} strokeWidth={1.5} />
      </span>
      <div>
        <h1 className="text-2xl font-medium text-text-primary">Lost in the table.</h1>
        <p className="mt-1 text-sm text-text-tertiary">
          That route doesn't exist (yet). Try the dashboard or open the command palette.
        </p>
      </div>
      <div className="flex gap-2">
        <Button variant="primary">
          <Link to="/">Back to dashboard</Link>
        </Button>
        <Button variant="secondary">
          <Link to="/trades">Trade log</Link>
        </Button>
      </div>
    </div>
  );
}
