import { forwardRef, useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { Input, type InputProps } from '../../components/Input.tsx';

/** Password field with a lock icon and a show/hide toggle. */
export const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputProps, 'type' | 'leftIcon' | 'rightIcon'>
>((props, ref) => {
  const [visible, setVisible] = useState(false);
  const Icon = visible ? EyeOff : Eye;
  return (
    <Input
      ref={ref}
      {...props}
      type={visible ? 'text' : 'password'}
      leftIcon={<Lock size={16} />}
      rightIcon={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          className="flex rounded text-ink-400 hover:text-ink-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
        >
          <Icon size={16} />
        </button>
      }
    />
  );
});

PasswordInput.displayName = 'PasswordInput';
