import { forwardRef, type InputHTMLAttributes } from 'react';
import { Check } from 'lucide-react';
import { cn } from '../lib/cn';

export interface CheckboxProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'type'
> {
  label?: string;
  invalid?: boolean;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, invalid, className, id, ...props }, ref) => {
    return (
      <label
        htmlFor={id}
        className="inline-flex cursor-pointer select-none items-center gap-2 font-sans text-sm text-ink-900"
      >
        <span className="relative flex h-5 w-5 shrink-0 items-center justify-center">
          <input
            ref={ref}
            id={id}
            type="checkbox"
            aria-invalid={invalid || undefined}
            className={cn(
              'peer h-5 w-5 appearance-none rounded-md border bg-white transition-colors',
              'checked:border-primary-600 checked:bg-primary-600',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-primary-500',
              'disabled:cursor-not-allowed disabled:opacity-50',
              invalid ? 'border-coral-500' : 'border-ink-400/40',
              className
            )}
            {...props}
          />
          <Check
            size={14}
            strokeWidth={3}
            aria-hidden="true"
            className="pointer-events-none absolute text-white opacity-0 transition-opacity peer-checked:opacity-100"
          />
        </span>
        {label}
      </label>
    );
  }
);

Checkbox.displayName = 'Checkbox';

/*
Usage — e.g. hospital connection consent:
<Checkbox
  id="consent"
  label="I agree to share my records with this hospital"
  checked={consented}
  onChange={(e) => setConsented(e.target.checked)}
/>
*/
