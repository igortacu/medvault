import * as Dialog from '@radix-ui/react-dialog';
import { Button } from './Button';
import { ModalContent } from './Modal';

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** "danger" for destructive actions (revoke, delete) — matches Button's danger variant. */
  variant?: 'danger' | 'primary';
  isLoading?: boolean;
  onConfirm: () => void;
}

/**
 * A controlled confirmation dialog for the destructive actions in the spec:
 * revoking a caregiver's access, revoking a institutions connection, removing
 * a profile from the sidebar switcher.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  isLoading,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <ModalContent title={title} description={description}>
        <div className="flex justify-end gap-3">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            isLoading={isLoading}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </ModalContent>
    </Dialog.Root>
  );
}

/*
Usage — revoking a institutions connection (Documents ingestion, Story 4):

const [confirmOpen, setConfirmOpen] = useState(false);

<ConfirmDialog
  open={confirmOpen}
  onOpenChange={setConfirmOpen}
  title="Revoke connection to City Hospital?"
  description="No further documents will be pulled from this institutions. This can't be undone."
  confirmLabel="Revoke"
  variant="danger"
  isLoading={isRevoking}
  onConfirm={() => revokeConnection(hospitalId)}
/>
*/
