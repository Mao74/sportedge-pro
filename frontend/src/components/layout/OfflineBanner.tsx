import { WifiOff } from 'lucide-react';
import { useOnlineStatus } from '@/hooks/useOnlineStatus';

export function OfflineBanner() {
  const online = useOnlineStatus();
  if (online) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-30 flex items-center justify-center gap-2 border-b border-accent-warn/30 bg-accent-warn-bg px-4 py-1.5 text-xs text-accent-warn"
    >
      <WifiOff size={12} strokeWidth={1.5} />
      <span>You're offline — changes will sync when the connection comes back.</span>
    </div>
  );
}
