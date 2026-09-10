import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cn } from '../lib/cn';

type IconButtonVariant = 'ghost' | 'outline' | 'danger';
type IconButtonSize = 'sm' | 'default' | 'lg';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  /** Required: an icon-only button must be labeled for screen readers. */
  'aria-label': string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
}

const base =
  'inline-flex items-center justify-center rounded-full transition-colors shrink-0 ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ' +
  'focus-visible:ring-primary-500 disabled:pointer-events-none disabled:opacity-50';

const variants: Record<IconButtonVariant, string> = {
  ghost: 'text-ink-600 hover:bg-primary-50',
  outline: 'border border-ink-400/30 text-ink-600 hover:bg-primary-50',
  danger: 'text-coral-500 hover:bg-coral-400/10',
};

const sizes: Record<IconButtonSize, string> = {
  sm: 'h-8 w-8',
  default: 'h-10 w-10',
  lg: 'h-12 w-12',
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      icon,
      variant = 'ghost',
      size = 'default',
      className,
      type = 'button',
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        className={cn(base, variants[variant], sizes[size], className)}
        {...props}
      >
        {icon}
      </button>
    );
  }
);

IconButton.displayName = 'IconButton';

/*
Usage — e.g. the delete button next to SidebarProfile:
<IconButton
  icon={<Trash2 size={16} />}
  aria-label="Remove profile"
  variant="danger"
  size="sm"
  onClick={() => removeProfile(profile.id)}
/>
*/
