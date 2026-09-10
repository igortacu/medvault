import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from '../lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  /** Set by FormField automatically when it has an error — can also be set directly. */
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ leftIcon, rightIcon, invalid, className, ...props }, ref) => {
    return (
      <div className="relative">
        {leftIcon && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400">
            {leftIcon}
          </span>
        )}
        <input
          ref={ref}
          aria-invalid={invalid || undefined}
          className={cn(
            'h-11 w-full rounded-xl border bg-white px-4 font-sans text-sm text-ink-900',
            'placeholder:text-ink-400 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary-500',
            'disabled:cursor-not-allowed disabled:bg-primary-50 disabled:text-ink-400',
            invalid
              ? 'border-coral-500 focus:ring-coral-500'
              : 'border-ink-400/30 focus:border-primary-500',
            leftIcon && 'pl-10',
            rightIcon && 'pr-10',
            className
          )}
          {...props}
        />
        {rightIcon && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400">
            {rightIcon}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

/*
Usage:
<Input type="email" placeholder="you@example.com" />
<Input leftIcon={<Search size={16} />} placeholder="Search records" />
<Input invalid placeholder="Phone number" />
*/
