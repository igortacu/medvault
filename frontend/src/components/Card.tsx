import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '../lib/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Adds hover/focus affordance for cards that act as navigation (e.g. a diagnostic row). */
  interactive?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ interactive, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-card bg-white p-5 shadow-card',
          interactive &&
            'cursor-pointer transition-shadow hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500',
          className
        )}
        {...props}
      />
    );
  }
);

Card.displayName = 'Card';

/*
Usage — a diagnostics list row (feature-level composition lives in
features/records, this stays a generic surface):

<Card interactive onClick={() => navigate(`/diagnostics/${id}`)}>
  <div className="flex items-center justify-between">
    <div>
      <p className="font-sans text-sm font-medium text-ink-900">{diagnostic.name}</p>
      <p className="text-sm text-ink-400">{formatDate(diagnostic.date)} · {diagnostic.specialty}</p>
    </div>
    <Badge variant="neutral">{diagnostic.sourceInstitution}</Badge>
  </div>
</Card>
*/
