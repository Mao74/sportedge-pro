/**
 * Obsidian conflicts drawer.
 *
 * Each unresolved conflict shows the file path, when it was detected, and a
 * side-by-side preview (truncated, scrollable) of DB version vs file version.
 * Three resolutions:
 *
 * - Keep DB    → discards the file content; next export regenerates the file
 *                from the DB.
 * - Keep file  → writes file_text into trade.notes_md.
 * - Merge…     → opens a modal with both sides shown; the trader writes the
 *                merged text and submits.
 */

import { useState } from 'react';
import { AlertTriangle, Check, FileText, GitMerge, Trash2 } from 'lucide-react';
import {
  Button,
  Drawer,
  EmptyState,
  Modal,
  Skeleton,
  useToast,
} from '@/components/primitives';
import { MarkdownEditor } from '@/components/notes/MarkdownEditor';
import { useConflicts, useResolveConflict, type ObsidianConflict } from '@/queries/obsidian';
import { ApiError } from '@/lib/api';
import { useUiStore } from '@/stores/ui';

const dateFmt = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
});

export function ConflictsDrawer() {
  const open = useUiStore((s) => s.conflictsOpen);
  const setOpen = useUiStore((s) => s.setConflictsOpen);
  const conflicts = useConflicts();
  const resolve = useResolveConflict();
  const toast = useToast();
  const [merging, setMerging] = useState<ObsidianConflict | null>(null);
  const [mergedText, setMergedText] = useState('');

  const submit = (id: string, resolution: 'keep_db' | 'keep_file' | 'merged', merged?: string) => {
    resolve.mutate(
      { id, resolution, ...(merged !== undefined ? { merged_text: merged } : {}) },
      {
        onSuccess: () => {
          toast.push({ tone: 'success', title: 'Conflict resolved.' });
          setMerging(null);
          setMergedText('');
        },
        onError: (err) => {
          const msg = err instanceof ApiError ? err.problem.detail || err.problem.title : 'Failed.';
          toast.push({ tone: 'error', title: 'Resolve failed.', description: msg });
        },
      },
    );
  };

  const startMerge = (c: ObsidianConflict) => {
    setMerging(c);
    // Pre-fill with the file version (the more recent intent) — the trader can edit.
    setMergedText(c.file_text ?? '');
  };

  return (
    <>
      <Drawer
        open={open}
        onClose={() => setOpen(false)}
        title="Obsidian conflicts"
        width={560}
      >
        {conflicts.isLoading ? (
          <div className="space-y-3">
            <Skeleton height={120} />
            <Skeleton height={120} />
          </div>
        ) : !conflicts.data || conflicts.data.length === 0 ? (
          <EmptyState
            icon={Check}
            title="No conflicts pending"
            description="The vault and DB are in sync. Conflicts appear when both sides edit the same trade between syncs."
          />
        ) : (
          <ul className="space-y-3">
            {conflicts.data.map((c) => (
              <li key={c.id} className="rounded-lg border border-accent-warn/30 bg-bg-overlay p-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle size={14} strokeWidth={1.5} className="mt-0.5 text-accent-warn" />
                  <div className="min-w-0 flex-1">
                    <div className="font-mono text-xs text-text-secondary truncate">
                      {c.path}
                    </div>
                    <div className="text-xs text-text-tertiary">
                      Detected {dateFmt.format(new Date(c.detected_at))}
                    </div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <DiffPane label="DB" body={c.db_text} updated={c.db_updated_at} />
                  <DiffPane label="File" body={c.file_text} updated={c.file_updated_at} />
                </div>

                <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => submit(c.id, 'keep_db')}
                    title="Discard the file content; export will regenerate it."
                  >
                    <Trash2 size={12} strokeWidth={1.5} /> Keep DB
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => submit(c.id, 'keep_file')}
                  >
                    <FileText size={12} strokeWidth={1.5} /> Keep file
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => startMerge(c)}
                  >
                    <GitMerge size={12} strokeWidth={1.5} /> Merge…
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Drawer>

      <Modal
        open={merging !== null}
        onClose={() => setMerging(null)}
        title="Manual merge"
        maxWidth={720}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setMerging(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={resolve.isPending}
              disabled={!mergedText.trim()}
              onClick={() => merging && submit(merging.id, 'merged', mergedText)}
            >
              Save merged
            </Button>
          </div>
        }
      >
        {merging ? (
          <div className="space-y-3">
            <div className="rounded-lg border border-border-subtle bg-bg-base p-3 text-xs">
              <div className="text-text-tertiary">File path</div>
              <div className="font-mono text-text-primary truncate">{merging.path}</div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <DiffPane label="DB version" body={merging.db_text} updated={merging.db_updated_at} />
              <DiffPane label="File version" body={merging.file_text} updated={merging.file_updated_at} />
            </div>
            <MarkdownEditor
              label="Merged result"
              value={mergedText}
              onChange={setMergedText}
              rows={10}
            />
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function DiffPane({
  label,
  body,
  updated,
}: {
  label: string;
  body: string | null;
  updated: string | null;
}) {
  return (
    <div className="rounded border border-border-subtle bg-bg-base p-2">
      <div className="mb-1 flex items-center justify-between text-2xs uppercase tracking-widest text-text-tertiary">
        <span>{label}</span>
        {updated ? <span className="font-mono">{dateFmt.format(new Date(updated))}</span> : null}
      </div>
      <pre className="max-h-32 overflow-auto whitespace-pre-wrap font-mono text-2xs text-text-secondary">
        {body || '(empty)'}
      </pre>
    </div>
  );
}
