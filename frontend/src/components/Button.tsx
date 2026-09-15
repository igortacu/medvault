import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../lib/cn';

type ButtonVariant = 'primary' | 'accent' | 'outline' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'default' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

const base =
  'inline-flex items-center justify-center gap-2 rounded-pill font-sans font-medium ' +
  'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ' +
  'focus-visible:ring-primary-500 disabled:pointer-events-none disabled:opacity-50';

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-primary-600 text-white hover:bg-primary-700',
  accent: 'bg-accent-400 text-ink-900 hover:bg-accent-500',
  outline:
    'border border-primary-600 text-primary-600 bg-transparent hover:bg-primary-50',
  ghost: 'text-ink-600 hover:bg-primary-50',
  danger: 'bg-coral-500 text-white hover:bg-coral-400',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm',
  default: 'h-11 px-6 text-sm',
  lg: 'h-12 px-8 text-base',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'default',
      isLoading,
      disabled,
      className,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        aria-busy={isLoading || undefined}
        className={cn(base, variants[variant], sizes[size], className)}
        {...props}
      >
        {isLoading && (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
