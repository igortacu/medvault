import {
  useRef,
  type ChangeEvent,
  type ClipboardEvent,
  type KeyboardEvent,
} from 'react';
import { cn } from '../lib/cn';

export interface OTPInputProps {
  length?: number;
  value: string;
  onChange: (value: string) => void;
  onComplete?: (value: string) => void;
  invalid?: boolean;
  disabled?: boolean;
  /** Set by FormField automatically when wrapped. */
  id?: string;
}

/**
 * Controlled OTP / MFA code input: one box per digit, auto-advances focus
 * on entry, supports backspace-to-previous, arrow-key navigation, and
 * pasting a full code across all boxes at once.
 */
export function OTPInput({
  length = 6,
  value,
  onChange,
  onComplete,
  invalid,
  disabled,
  id,
}: OTPInputProps) {
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);
  const digits = Array.from({ length }, (_, i) => value[i] ?? '');

  function commit(nextDigits: string[]) {
    const nextValue = nextDigits.join('');
    onChange(nextValue);
    if (nextValue.length === length && !nextValue.includes('')) {
      onComplete?.(nextValue);
    }
  }

  function handleChange(index: number, e: ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, '');
    const next = digits.slice();

    if (!raw) {
      next[index] = '';
      commit(next);
      return;
    }

    next[index] = raw[raw.length - 1];
    commit(next);
    if (index < length - 1) inputsRef.current[index + 1]?.focus();
  }

  function handleKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputsRef.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    const pasted = e.clipboardData
      .getData('text')
      .replace(/\D/g, '')
      .slice(0, length);
    if (!pasted) return;

    const next = Array.from({ length }, (_, i) => pasted[i] ?? '');
    commit(next);

    const lastFilled = Math.min(pasted.length, length) - 1;
    inputsRef.current[lastFilled]?.focus();
  }

  return (
    <div className="flex gap-2" role="group" aria-label="One-time passcode">
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            inputsRef.current[index] = el;
          }}
          id={index === 0 ? id : undefined}
          value={digit}
          onChange={(e) => handleChange(index, e)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          onPaste={handlePaste}
          disabled={disabled}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={1}
          aria-invalid={invalid || undefined}
          aria-label={`Digit ${index + 1} of ${length}`}
          className={cn(
            'h-12 w-10 rounded-xl border text-center font-sans text-lg font-medium text-ink-900 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary-500',
            'disabled:cursor-not-allowed disabled:bg-primary-50 disabled:text-ink-400',
            invalid
              ? 'border-coral-500 focus:ring-coral-500'
              : 'border-ink-400/30 focus:border-primary-500'
          )}
        />
      ))}
    </div>
  );
}

/*
Usage:
const [code, setCode] = useState("");

<OTPInput
  length={6}
  value={code}
  onChange={setCode}
  onComplete={(fullCode) => verifyMfaCode(fullCode)}
/>
*/
