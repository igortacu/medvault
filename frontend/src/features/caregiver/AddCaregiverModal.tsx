import { useState } from 'react';
import { UserPlus } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';
import { useTranslation } from 'react-i18next';
import { Modal, ModalContent, ModalTrigger } from '../../components/Modal';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { FormField } from '../../components/Formfield';
import { Checkbox } from '../../components/CheckBox';
import { useToast } from '../../components/Toast';
import { useCaregiverStore } from '../../store/caregiverStore';
import type { DataCategory } from '../../api/types';
import { categoryLabel, DATA_CATEGORIES as CATEGORIES } from './categoryLabels';

interface AddCaregiverModalProps {
  patientId: string;
}

function sameName(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

export function AddCaregiverModal({ patientId }: AddCaregiverModalProps) {
  const { t } = useTranslation(['caregiver', 'common']);
  const findUserByPhone = useCaregiverStore((state) => state.findUserByPhone);
  const inviteCaregiver = useCaregiverStore((state) => state.inviteCaregiver);
  const { showToast } = useToast();

  const [open, setOpen] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [birthDate, setBirthDate] = useState('');
  const [phone, setPhone] = useState('');
  const [categories, setCategories] = useState<Record<DataCategory, boolean>>(
    {} as Record<DataCategory, boolean>
  );
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function reset() {
    setFirstName('');
    setLastName('');
    setBirthDate('');
    setPhone('');
    setCategories({} as Record<DataCategory, boolean>);
    setError(null);
  }

  function toggleCategory(category: DataCategory) {
    setCategories((prev) => ({ ...prev, [category]: !prev[category] }));
  }

  async function handleSubmit() {
    setError(null);

    if (!firstName || !lastName || !birthDate || !phone) {
      setError(t('add.fillAll'));
      return;
    }

    setIsSubmitting(true);
    try {
      const candidate = await findUserByPhone(phone);
      if (!candidate) {
        setError(t('add.noAccount'));
        return;
      }
      if (
        !sameName(candidate.firstName, firstName) ||
        !sameName(candidate.lastName, lastName) ||
        candidate.birthDate !== birthDate
      ) {
        setError(t('add.mismatch'));
        return;
      }

      const selectedCategories = CATEGORIES.filter((c) => categories[c]);
      await inviteCaregiver({
        patientId,
        caregiverUserId: candidate.userId,
        permissions: selectedCategories,
      });

      showToast({
        variant: 'success',
        title: t('add.sent'),
        description: t('add.sentDescription', {
          name: `${firstName} ${lastName}`,
        }),
      });
      reset();
      setOpen(false);
    } catch {
      showToast({
        variant: 'error',
        title: t('add.failed'),
        description: t('common:pleaseTryAgain'),
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) reset();
      }}
    >
      <ModalTrigger asChild>
        <Button variant="primary">
          <UserPlus size={16} />
          {t('add.button')}
        </Button>
      </ModalTrigger>
      <ModalContent
        title={t('add.title')}
        description={t('add.description')}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label={t('add.firstName')} required>
              <Input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Ana"
              />
            </FormField>
            <FormField label={t('add.lastName')} required>
              <Input
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Popescu"
              />
            </FormField>
          </div>

          <FormField label={t('add.dateOfBirth')} required>
            <Input
              type="date"
              value={birthDate}
              onChange={(e) => setBirthDate(e.target.value)}
            />
          </FormField>

          <FormField
            label={t('add.phone')}
            required
            error={error ?? undefined}
          >
            <Input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+373 6XXXXXXX"
            />
          </FormField>

          <div>
            <p className="font-sans text-sm font-medium text-ink-900">
              {t('add.access')}
            </p>
            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {CATEGORIES.map((category) => (
                <Checkbox
                  key={category}
                  id={`invite-permission-${category}`}
                  label={categoryLabel(category)}
                  checked={categories[category] ?? false}
                  onChange={() => toggleCategory(category)}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <Dialog.Close asChild>
            <Button variant="ghost">{t('common:cancel')}</Button>
          </Dialog.Close>
          <Button
            variant="primary"
            isLoading={isSubmitting}
            onClick={handleSubmit}
          >
            {t('add.submit')}
          </Button>
        </div>
      </ModalContent>
    </Modal>
  );
}
