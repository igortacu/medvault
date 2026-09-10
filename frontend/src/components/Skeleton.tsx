import type { HTMLAttributes } from 'react';
import { cn } from '../lib/cn';

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {}

/** A single pulsing placeholder block — compose these for any loading shape. */
export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse rounded-xl bg-primary-100', className)}
      {...props}
    />
  );
}

/**
 * Matches Card's shape — drop this in while a category list
 * (diagnostics/prescriptions/certificates) is loading via TanStack Query.
 */
export function SkeletonListItem() {
  return (
    <div className="rounded-card bg-white p-5 shadow-card">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="mt-2 h-3 w-1/2" />
    </div>
  );
}

/*
Usage:
const { data, isLoading } = useDiagnostics();

if (isLoading) {
  return (
    <div className="space-y-3">
      <SkeletonListItem />
      <SkeletonListItem />
      <SkeletonListItem />
    </div>
  );
}
*/
