import {
  useRef,
  type ChangeEvent,
  type ClipboardEvent,
  type KeyboardEvent,
} from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
      // Clearing a middle box must not shift later digits left: drop the tail too.
      commit(next.slice(0, index));
      return;
    }

    // SMS autofill / password managers put the whole code into one box.
    if (raw.length > 1) {
      fillFrom(0, raw);
      return;
    }

    // Digits are always entered left to right, so there are never gaps in `value`.
    const firstEmpty = digits.findIndex((d) => !d);
    const target = firstEmpty === -1 ? index : Math.min(index, firstEmpty);
    next[target] = raw;
    commit(next.slice(0, Math.max(target + 1, digits.filter(Boolean).length)));
    if (target < length - 1) inputsRef.current[target + 1]?.focus();
  }

  function fillFrom(start: number, text: string) {
    const next = digits.slice(0, start);
    for (const ch of text.slice(0, length - start)) next.push(ch);
    commit(next);
    inputsRef.current[Math.min(next.length, length - 1)]?.focus();
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
    <div className="flex gap-2" role="group" aria-label={t('otp.group')}>
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
          // Select the digit on focus so typing replaces it (the box allows more than
          // one character only so one-time-code autofill can drop the whole code in).
          onFocus={(e) => e.target.select()}
          disabled={disabled}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={length}
          aria-invalid={invalid || undefined}
          aria-label={t('otp.digit', { index: index + 1, length })}
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
