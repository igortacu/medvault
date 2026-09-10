import type { HTMLAttributes } from 'react';
import { cn } from '../lib/cn';

type BadgeVariant = 'neutral' | 'success' | 'warning' | 'danger';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variants: Record<BadgeVariant, string> = {
  neutral: 'bg-ink-400/10 text-ink-600',
  success: 'bg-primary-100 text-primary-700',
  warning: 'bg-accent-200 text-accent-600',
  danger: 'bg-coral-400/15 text-coral-500',
};

export function Badge({
  variant = 'neutral',
  className,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 font-sans text-xs font-medium',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

/*
Usage, mapped to actual states in the spec:
<Badge variant="neutral">Previous</Badge>
<Badge variant="warning">Pending</Badge>               // hospital connection request
<Badge variant="success">Connected</Badge>
<Badge variant="danger">Revoked</Badge>
<Badge variant="neutral">City Hospital</Badge>          // source institution (Story 8)
*/
