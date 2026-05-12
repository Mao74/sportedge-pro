import { Skeleton } from '@/components/primitives';
import { TradeForm } from '@/components/trades/TradeForm';
import { useStrategies } from '@/queries/dashboard';

export default function NewTrade() {
  const { data: strategies, isLoading } = useStrategies();

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <div className="text-2xs uppercase tracking-widest text-text-tertiary">Trades</div>
        <h1 className="text-2xl font-medium text-text-primary">New trade</h1>
        <p className="text-sm text-text-secondary">
          Pick a strategy, fill the universal fields, and choose how to log the close.
        </p>
      </header>

      {isLoading || !strategies ? (
        <div className="space-y-4">
          <Skeleton height={32} />
          <Skeleton height={120} />
          <Skeleton height={120} />
        </div>
      ) : strategies.filter((s) => s.is_active).length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-subtle p-8 text-center text-sm text-text-tertiary">
          No active strategies — create one in /strategies first.
        </div>
      ) : (
        <TradeForm strategies={strategies.filter((s) => s.is_active)} />
      )}
    </div>
  );
}
