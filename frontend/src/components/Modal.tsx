// npm install @radix-ui/react-dialog
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '../lib/cn';

/**
 * Modal = Radix's Dialog primitives, restyled with Tailwind and given a
 * consistent header (title + description + close button). Radix handles
 * focus trapping, Escape-to-close, outside-click, and returning focus to
 * the trigger on close — the behavior that's genuinely worth not hand-rolling.
 */
export const Modal = Dialog.Root;
export const ModalTrigger = Dialog.Trigger;

export interface ModalContentProps {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

export function ModalContent({
  title,
  description,
  children,
  className,
}: ModalContentProps) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-ink-900/40" />
      <Dialog.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2',
          'rounded-card bg-white p-6 shadow-card focus:outline-none',
          className
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <Dialog.Title className="font-display text-lg font-semibold text-ink-900">
              {title}
            </Dialog.Title>
            {description && (
              <Dialog.Description className="mt-1 text-sm text-ink-600">
                {description}
              </Dialog.Description>
            )}
          </div>
          <Dialog.Close
            aria-label="Close"
            className="shrink-0 rounded-full p-1 text-ink-400 transition-colors hover:bg-primary-50 hover:text-ink-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
          >
            <X size={18} />
          </Dialog.Close>
        </div>
        <div className="mt-4">{children}</div>
      </Dialog.Content>
    </Dialog.Portal>
  );
}

/*
Usage — the institutions-connection consent screen (Story: Connect to a institutions):

<Modal>
  <ModalTrigger asChild>
    <Button variant="primary">Connect institutions</Button>
  </ModalTrigger>
  <ModalContent
    title="Connect to City Hospital"
    description="CureVault will request your diagnostics and prescriptions using your IDNP. No other documents is shared."
  >
    <div className="flex justify-end gap-3">
      <Dialog.Close asChild>
        <Button variant="ghost">Cancel</Button>
      </Dialog.Close>
      <Button variant="primary" onClick={confirmConnection}>I consent, connect</Button>
    </div>
  </ModalContent>
</Modal>

Note: install "tailwindcss-animate" and add documents-[state=open]/documents-[state=closed]
variants later if you want enter/exit transitions — Radix exposes the state,
this version just keeps things dependency-free for now.
*/
