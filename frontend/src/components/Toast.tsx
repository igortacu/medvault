// npm install @radix-ui/react-toast
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import * as RadixToast from '@radix-ui/react-toast';
import { CheckCircle2, Info, X, XCircle } from 'lucide-react';
import { cn } from '../lib/cn';

type ToastVariant = 'success' | 'error' | 'info';

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (toast: Omit<ToastItem, 'id'>) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Call from any component to fire a toast — no prop drilling needed. */
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}

const variantStyles: Record<ToastVariant, string> = {
  success: 'border-primary-600/20',
  error: 'border-coral-500/30',
  info: 'border-ink-400/20',
};

const variantIcons: Record<ToastVariant, ReactNode> = {
  success: (
    <CheckCircle2 size={18} className="text-primary-600" aria-hidden="true" />
  ),
  error: <XCircle size={18} className="text-coral-500" aria-hidden="true" />,
  info: <Info size={18} className="text-ink-400" aria-hidden="true" />,
};

let toastCounter = 0;

/** Wrap the app (or a layout) once with this — everything below can call useToast(). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = String(toastCounter++);
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  function dismiss(id: string) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <ToastContext.Provider value={{ showToast }}>
      <RadixToast.Provider swipeDirection="right" duration={4000}>
        {children}
        {toasts.map((toast) => (
          <RadixToast.Root
            key={toast.id}
            onOpenChange={(open) => !open && dismiss(toast.id)}
            className={cn(
              'flex items-start gap-3 rounded-xl border bg-white p-4 shadow-card',
              'documents-[swipe=end]:translate-x-full',
              variantStyles[toast.variant]
            )}
          >
            {variantIcons[toast.variant]}
            <div className="flex-1">
              <RadixToast.Title className="font-sans text-sm font-medium text-ink-900">
                {toast.title}
              </RadixToast.Title>
              {toast.description && (
                <RadixToast.Description className="mt-0.5 text-sm text-ink-600">
                  {toast.description}
                </RadixToast.Description>
              )}
            </div>
            <RadixToast.Close
              aria-label="Dismiss"
              className="text-ink-400 hover:text-ink-600"
            >
              <X size={16} />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2 outline-none" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

/*
Usage — after an upload attempt (Documents ingestion, Story 1), which the spec
requires to be logged and to give clear success/error feedback:

const { showToast } = useToast();

try {
  await uploadDocument(file);
  showToast({ variant: "success", title: "Document uploaded", description: "Added to Diagnostics." });
} catch {
  showToast({ variant: "error", title: "Upload failed", description: "Please try again." });
}
*/
