import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { ModalContent } from '../../components/Modal';
import { Button } from '../../components/Button';
import { cn } from '../../lib/cn';
import type { Institution } from '../../api/types';
import { ConnectForm } from './ConnectForm';

export interface ConnectInstitutionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Choices for "Add institution", or the single institution to reconnect. */
  institutions: Institution[];
  mode: 'add' | 'reconnect';
  isSubmitting?: boolean;
  cooldownSeconds?: number;
  onConnect: (institutionId: string, idnp: string) => void;
}

/**
 * Connects one institution: "Add institution" picks it from the catalogue
 * (never a free-form address), reconnect has it fixed.
 */
export function ConnectInstitutionModal({
  open,
  onOpenChange,
  institutions,
  mode,
  isSubmitting,
  cooldownSeconds,
  onConnect,
}: ConnectInstitutionModalProps) {
  const [pickedId, setPickedId] = useState<string | null>(null);
  const selected =
    mode === 'reconnect'
      ? institutions[0]
      : institutions.find((i) => i.id === pickedId);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setPickedId(null);
      }}
    >
      <ModalContent
        className="max-h-[calc(100dvh-2rem)] max-w-lg overflow-y-auto"
        title={
          mode === 'add'
            ? 'Add an institution'
            : `Reconnect ${institutions[0]?.name ?? ''}`
        }
        description={
          mode === 'add'
            ? 'Private clinics are only connected when you add them.'
            : 'Enter your IDNP again so the institution can find your records.'
        }
      >
        {/* Radix unmounts the content on close, so the IDNP is dropped too. */}
        <ConnectForm
          institutions={selected ? [selected] : []}
          submitLabel="I consent, connect"
          isSubmitting={isSubmitting}
          cooldownSeconds={cooldownSeconds}
          onSubmit={(idnp) => selected && onConnect(selected.id, idnp)}
          secondaryAction={
            <Dialog.Close asChild>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </Dialog.Close>
          }
        >
          {mode === 'add' && (
            <fieldset>
              <legend className="font-sans text-sm font-medium text-ink-900">
                Institution
              </legend>
              {institutions.length === 0 ? (
                <p className="mt-2 text-sm text-ink-400">
                  Every institution in the catalogue is already connected.
                </p>
              ) : (
                <div className="mt-2 space-y-2">
                  {institutions.map((institution) => (
                    <label
                      key={institution.id}
                      className={cn(
                        'flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm transition-colors',
                        pickedId === institution.id
                          ? 'border-primary-600 bg-primary-50'
                          : 'border-ink-400/25 hover:bg-primary-50/50'
                      )}
                    >
                      <input
                        type="radio"
                        name="institution"
                        value={institution.id}
                        checked={pickedId === institution.id}
                        onChange={() => setPickedId(institution.id)}
                        className="h-4 w-4 accent-primary-600"
                      />
                      <span className="text-ink-900">{institution.name}</span>
                      {institution.city && (
                        <span className="ml-auto text-ink-400">
                          {institution.city}
                        </span>
                      )}
                    </label>
                  ))}
                </div>
              )}
            </fieldset>
          )}
        </ConnectForm>
      </ModalContent>
    </Dialog.Root>
  );
}
