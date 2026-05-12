import { Link } from 'react-router-dom';
import { useObsidianStatus } from '@/queries/obsidian';
import { useUiStore } from '@/stores/ui';
import { cn } from '@/lib/cn';

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  hour: '2-digit',
  minute: '2-digit',
});

function relTime(iso: string | null): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60_000);
  if (min < 1) return 'just now';
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return dateFmt.format(new Date(iso));
}

export function ObsidianStatusBadge() {
  const { data } = useObsidianStatus({ refetchInterval: 30_000 });
  const openConflicts = useUiStore((s) => s.setConflictsOpen);
  if (!data || !data.enabled) return null;

  const hasConflicts = data.conflict_count > 0;
  const dotClass = data.last_error
    ? 'bg-accent-loss'
    : hasConflicts
      ? 'bg-accent-warn'
      : 'bg-accent-gain';

  const title =
    data.last_error
      ? `Error: ${data.last_error}`
      : hasConflicts
        ? `${data.conflict_count} conflict${data.conflict_count === 1 ? '' : 's'} pending`
        : `Synced ${relTime(data.last_sync_at)}`;

  const inner = (
    <>
      <span className={cn('h-2 w-2 rounded-full', dotClass)} aria-hidden />
      <span className="font-mono">obsidian</span>
      {hasConflicts ? (
        <span className="font-mono text-accent-warn">{data.conflict_count}</span>
      ) : null}
    </>
  );

  // If there are conflicts to resolve, the click opens the drawer in-place;
  // otherwise it falls back to the Settings page.
  if (hasConflicts) {
    return (
      <button
        type="button"
        title={title}
        aria-label={`Obsidian status — ${title}`}
        onClick={() => openConflicts(true)}
        className="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-overlay px-2.5 py-1.5 text-xs text-text-tertiary hover:text-text-secondary"
      >
        {inner}
      </button>
    );
  }

  return (
    <Link
      to="/settings"
      title={title}
      aria-label={`Obsidian status — ${title}`}
      className="flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-overlay px-2.5 py-1.5 text-xs text-text-tertiary hover:text-text-secondary"
    >
      {inner}
    </Link>
  );
}
