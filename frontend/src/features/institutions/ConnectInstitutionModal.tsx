import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useTranslation } from 'react-i18next';
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
  onConnect,
}: ConnectInstitutionModalProps) {
  const { t } = useTranslation(['institutions', 'common']);
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
            ? t('modal.addTitle')
            : t('modal.reconnectTitle', { name: institutions[0]?.name ?? '' })
        }
        description={
          mode === 'add'
            ? t('modal.addDescription')
            : t('modal.reconnectDescription')
        }
      >
        {/* Radix unmounts the content on close, so the IDNP is dropped too. */}
        <ConnectForm
          institutions={selected ? [selected] : []}
          submitLabel={t('consentSubmit')}
          isSubmitting={isSubmitting}
          onSubmit={(idnp) => selected && onConnect(selected.id, idnp)}
          secondaryAction={
            <Dialog.Close asChild>
              <Button type="button" variant="ghost">
                {t('common:cancel')}
              </Button>
            </Dialog.Close>
          }
        >
          {mode === 'add' && (
            <fieldset>
              <legend className="font-sans text-sm font-medium text-ink-900">
                {t('modal.institution')}
              </legend>
              {institutions.length === 0 ? (
                <p className="mt-2 text-sm text-ink-400">
                  {t('modal.allConnected')}
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
