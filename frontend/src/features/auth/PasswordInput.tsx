import { forwardRef, useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Input, type InputProps } from '../../components/Input.tsx';

/** Password field with a lock icon and a show/hide toggle. */
export const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputProps, 'type' | 'leftIcon' | 'rightIcon'>
>((props, ref) => {
  const { t } = useTranslation('auth');
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
          aria-label={visible ? t('hidePassword') : t('showPassword')}
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
