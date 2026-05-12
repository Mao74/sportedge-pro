/**
 * Import / export CSV panel.
 *
 * Flow:
 *  1. Pick a file (button or drag&drop)
 *  2. Auto-runs a dry-run preview → shows parsed / valid / errored row counts
 *  3. Commit button (disabled while there are 0 valid rows)
 *
 * Export: single-click, streams the blob and triggers a download.
 */

import { useCallback, useRef, useState } from 'react';
import { Upload, Download, FileText, Check, AlertOctagon } from 'lucide-react';
import { Button, Card, Skeleton, useToast } from '@/components/primitives';
import { ApiError } from '@/lib/api';
import {
  exportTradesCsv,
  useImportTradesCsv,
  type CsvImportResult,
} from '@/queries/csv_io';
import { cn } from '@/lib/cn';

export function DataIoPanel() {
  const toast = useToast();
  const importMut = useImportTradesCsv();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CsvImportResult | null>(null);
  const [exportingCsv, setExportingCsv] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const onExport = async () => {
    setExportingCsv(true);
    try {
      await exportTradesCsv();
      toast.push({ tone: 'success', title: 'Export downloaded.' });
    } catch (err) {
      const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
      toast.push({ tone: 'error', title: 'Export failed.', description: msg });
    } finally {
      setExportingCsv(false);
    }
  };

  const runDryRun = useCallback(
    async (f: File) => {
      setFile(f);
      setPreview(null);
      try {
        const res = await importMut.mutateAsync({ file: f, dryRun: true });
        setPreview(res);
      } catch (err) {
        const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
        toast.push({ tone: 'error', title: 'Preview failed.', description: msg });
      }
    },
    [importMut, toast],
  );

  const onPick = (f: File | undefined | null) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.csv')) {
      toast.push({ tone: 'warn', title: 'Only .csv files supported.' });
      return;
    }
    runDryRun(f);
  };

  const onCommit = async () => {
    if (!file) return;
    try {
      const res = await importMut.mutateAsync({ file, dryRun: false });
      toast.push({
        tone: 'success',
        title: `${res.inserted} trade${res.inserted === 1 ? '' : 's'} imported.`,
        description: res.errors.length > 0 ? `${res.errors.length} row(s) skipped.` : undefined,
      });
      // Refresh preview so the user sees the committed state if they re-run.
      setPreview({ ...res });
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
    } catch (err) {
      const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
      toast.push({ tone: 'error', title: 'Import failed.', description: msg });
    }
  };

  return (
    <Card
      header={
        <>
          <span className="flex items-center gap-2 text-text-primary">
            <FileText size={14} strokeWidth={1.5} />
            Import / Export
          </span>
          <span className="text-xs text-text-tertiary">
            CSV — same schema in both directions for clean round-trips.
          </span>
        </>
      }
    >
      <div className="space-y-5">
        {/* Export */}
        <div className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-overlay px-4 py-3">
          <div>
            <div className="text-sm text-text-primary">Export trades as CSV</div>
            <div className="text-xs text-text-tertiary">
              Full history. Header row + one row per trade. Tags pipe-separated;
              strategy_data is JSON.
            </div>
          </div>
          <Button
            variant="secondary"
            size="md"
            loading={exportingCsv}
            onClick={onExport}
          >
            <Download size={14} strokeWidth={1.5} />
            Export now
          </Button>
        </div>

        {/* Import */}
        <div>
          <div className="mb-2 text-2xs uppercase tracking-widest text-text-tertiary">
            Import from CSV
          </div>

          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              onPick(e.dataTransfer.files?.[0]);
            }}
            className={cn(
              'flex flex-col items-center gap-2 rounded-lg border-2 border-dashed bg-bg-overlay px-4 py-8 text-center text-sm cursor-pointer transition-colors',
              dragging
                ? 'border-accent-brand text-accent-brand'
                : 'border-border-subtle text-text-tertiary hover:border-border-strong',
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={(e) => onPick(e.target.files?.[0])}
            />
            <Upload size={18} strokeWidth={1.5} />
            <span>
              <span className="text-text-primary font-medium">Click to choose</span> or drop a CSV here.
            </span>
            <span className="font-mono text-2xs">
              Header must match the export schema (24 columns).
            </span>
            {file ? (
              <span className="mt-2 inline-flex items-center gap-2 rounded bg-bg-base px-2 py-1 text-xs text-text-secondary">
                <FileText size={12} strokeWidth={1.5} />
                {file.name}
              </span>
            ) : null}
          </label>

          {importMut.isPending && !preview ? (
            <div className="mt-3"><Skeleton height={60} /></div>
          ) : null}

          {preview ? (
            <div className="mt-4 space-y-3 rounded-lg border border-border-subtle bg-bg-overlay p-4">
              <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
                <Stat label="Parsed" value={String(preview.parsed_rows)} />
                <Stat
                  label="Valid"
                  value={String(preview.valid_rows)}
                  tone={preview.valid_rows > 0 ? 'gain' : 'zero'}
                />
                <Stat
                  label="Errors"
                  value={String(preview.errors.length)}
                  tone={preview.errors.length > 0 ? 'loss' : 'zero'}
                />
                {preview.inserted > 0 ? (
                  <Stat label="Inserted" value={String(preview.inserted)} tone="gain" />
                ) : null}
                <span
                  className={cn(
                    'ml-auto inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs',
                    preview.dry_run
                      ? 'bg-accent-info-bg text-accent-info'
                      : 'bg-accent-gain-bg text-accent-gain',
                  )}
                >
                  {preview.dry_run ? (
                    <>
                      <FileText size={11} strokeWidth={1.5} /> Dry-run
                    </>
                  ) : (
                    <>
                      <Check size={11} strokeWidth={1.5} /> Committed
                    </>
                  )}
                </span>
              </div>

              {preview.errors.length > 0 ? (
                <details className="text-xs">
                  <summary className="cursor-pointer text-accent-loss">
                    <AlertOctagon size={11} strokeWidth={1.5} className="-mt-0.5 mr-1 inline" />
                    {preview.errors.length} row error{preview.errors.length === 1 ? '' : 's'} — click to expand
                  </summary>
                  <ul className="mt-2 max-h-48 overflow-y-auto space-y-1 font-mono text-text-secondary">
                    {preview.errors.slice(0, 50).map((e, i) => (
                      <li key={`${e.row_index}-${i}`}>
                        <span className="text-text-tertiary">row {e.row_index}</span>
                        {e.column ? <span className="text-text-tertiary"> · {e.column}</span> : null}
                        <span> — {e.detail}</span>
                      </li>
                    ))}
                    {preview.errors.length > 50 ? (
                      <li className="text-text-tertiary">
                        … {preview.errors.length - 50} more
                      </li>
                    ) : null}
                  </ul>
                </details>
              ) : null}

              {preview.dry_run && file ? (
                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    size="md"
                    onClick={onCommit}
                    loading={importMut.isPending}
                    disabled={preview.valid_rows === 0}
                  >
                    Commit {preview.valid_rows} row{preview.valid_rows === 1 ? '' : 's'}
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function Stat({
  label,
  value,
  tone = 'zero',
}: {
  label: string;
  value: string;
  tone?: 'gain' | 'loss' | 'zero';
}) {
  const cls =
    tone === 'gain'
      ? 'text-accent-gain'
      : tone === 'loss'
        ? 'text-accent-loss'
        : 'text-text-primary';
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-xs uppercase tracking-widest text-text-tertiary">{label}</span>
      <span className={`font-mono tabular-nums text-sm ${cls}`}>{value}</span>
    </div>
  );
}
