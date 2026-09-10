import { useId, cloneElement, type ReactElement } from 'react';

interface FieldProps {
  id?: string;
  'aria-describedby'?: string;
  invalid?: boolean;
}

export interface FormFieldProps {
  label: string;
  htmlFor?: string;
  error?: string;
  hint?: string;
  required?: boolean;
  /** A single form control — Input, Checkbox, OTPInput, etc. */
  children: ReactElement<FieldProps>;
}

/**
 * Wraps a single form control with a label and error/hint text, wiring up
 * id + aria-describedby + invalid automatically so every field in the app
 * gets the same accessible pattern without repeating it per screen.
 */
export function FormField({
  label,
  htmlFor,
  error,
  hint,
  required,
  children,
}: FormFieldProps) {
  const generatedId = useId();
  const id = htmlFor ?? generatedId;
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;

  const field = cloneElement(children, {
    id,
    'aria-describedby': describedBy,
    invalid: Boolean(error),
  });

  return (
    <div className="space-y-1.5">
      <label
        htmlFor={id}
        className="block font-sans text-sm font-medium text-ink-900"
      >
        {label}
        {required && <span className="ml-0.5 text-coral-500">*</span>}
      </label>

      {field}

      {error ? (
        <p id={`${id}-error`} className="text-sm text-coral-500">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-sm text-ink-400">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/*
Usage with React Hook Form + Zod:
<FormField label="Email" required error={errors.email?.message}>
  <Input type="email" {...register("email")} />
</FormField>
*/
