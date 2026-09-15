import type { ReactNode } from 'react';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  /** e.g. a "Clear filters" or "Upload document" Button. */
  action?: ReactNode;
}

/**
 * One reusable empty state for every "no records yet" / "no results" case
 * in the spec: empty diagnostics, prescriptions, certificates, "other info",
 * and filtered views with no matches.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-ink-400/25 bg-primary-50/40 px-6 py-12 text-center">
      {icon && <div className="text-ink-400">{icon}</div>}
      <div>
        <p className="font-display text-base font-semibold text-ink-900">
          {title}
        </p>
        {description && (
          <p className="mt-1 text-sm text-ink-600">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/*
Usage — no diagnostics yet:
<EmptyState
  icon={<FileX size={32} />}
  title="No diagnostics yet"
  description="Diagnostics added by a connected institutions, or uploaded by you, will appear here."
/>

Usage — filtered view with no matches (Filtering medical documents, Story 6):
<EmptyState
  title="No results"
  description="No diagnostics match the selected filters."
  action={<Button variant="ghost" onClick={clearFilters}>Clear filters</Button>}
/>
*/
