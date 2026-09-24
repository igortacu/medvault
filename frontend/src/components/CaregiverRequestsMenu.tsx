import { useEffect, useState } from 'react';
import { Bell, Check, ChevronRight, X } from 'lucide-react';
import { useDatasetStore } from '../store/datasetStore';
import { useCaregiverStore } from '../store/caregiverStore';
import { IconButton } from './IconButton';
import { Button } from './Button';
import { Avatar } from './Avatar';
import { Modal, ModalContent } from './Modal';
import { useToast } from './Toast';
import { CATEGORY_LABELS } from '../features/caregiver/categoryLabels';
import { formatDate } from '../utils/formatDate';
import { cn } from '../lib/cn';
import type { CareRecipient } from '../api/caregiver.types';

interface CaregiverRequestsMenuProps {
  className?: string;
  /** Which side of the bell the panel opens toward. */
  panelSide?: 'above' | 'below';
  /** Lets the trigger match a dark (sidebar) or light (mobile header) surface. */
  buttonClassName?: string;
}

export function CaregiverRequestsMenu({
  className,
  panelSide = 'below',
  buttonClassName,
}: CaregiverRequestsMenuProps) {
  const [open, setOpen] = useState(false);
  const currentUser = useDatasetStore((state) => state.currentUser);
  const usersICareFor = useCaregiverStore((state) => state.usersICareFor);
  const loadUsersICareFor = useCaregiverStore(
    (state) => state.loadUsersICareFor
  );
  const respondToCaregiverRequest = useCaregiverStore(
    (state) => state.respondToCaregiverRequest
  );
  const { showToast } = useToast();
  const [selectedRequest, setSelectedRequest] = useState<CareRecipient | null>(
    null
  );
  const [responding, setResponding] = useState<'accept' | 'decline' | null>(
    null
  );

  useEffect(() => {
    if (currentUser) loadUsersICareFor(currentUser.id);
  }, [currentUser, loadUsersICareFor]);

  const pendingRequests = usersICareFor.filter((r) => r.status === 'pending');

  function openRequest(request: CareRecipient) {
    setOpen(false);
    setSelectedRequest(request);
  }

  async function handleRespond(accept: boolean) {
    if (!selectedRequest) return;
    setResponding(accept ? 'accept' : 'decline');
    await respondToCaregiverRequest({
      linkId: selectedRequest.linkId,
      accept,
    });
    setResponding(null);

    // The store swallows errors into `error` rather than rethrowing.
    if (useCaregiverStore.getState().error) {
      showToast({
        variant: 'error',
        title: 'Failed to respond',
        description: 'Please try again.',
      });
      return;
    }
    showToast({
      variant: 'success',
      title: accept
        ? `${selectedRequest.name} added to your recipients`
        : 'Request declined',
    });
    setSelectedRequest(null);
  }

  const sharedCategories =
    selectedRequest?.permissions.filter((p) => p.granted) ?? [];

  return (
    <div className={cn('relative', className)}>
      <IconButton
        icon={<Bell size={18} strokeWidth={2} />}
        aria-label="Caregiver requests"
        onClick={() => setOpen((prev) => !prev)}
        className={cn('relative', buttonClassName)}
      />
      {pendingRequests.length > 0 && (
        <span className="pointer-events-none absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-coral-500 text-[10px] font-semibold text-white">
          {pendingRequests.length}
        </span>
      )}

      {open && (
        <div
          className="fixed inset-0 z-40"
          onMouseDown={() => setOpen(false)}
        />
      )}

      {open && (
        <div
          className={cn(
            'absolute left-0 z-50 w-80 rounded-card border border-ink-400/20 bg-white p-4 text-left shadow-lg',
            panelSide === 'above' ? 'bottom-full mb-2' : 'top-full mt-2'
          )}
        >
          <p className="font-display text-sm font-semibold text-ink-900">
            Caregiver requests
          </p>

          {pendingRequests.length === 0 ? (
            <p className="mt-3 text-sm text-ink-400">No pending requests.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {pendingRequests.map((request) => (
                <button
                  key={request.linkId}
                  type="button"
                  onClick={() => openRequest(request)}
                  className="flex w-full items-center gap-3 rounded-xl border border-ink-400/10 p-3 text-left transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
                >
                  <Avatar name={request.name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-900">
                      {request.name}
                    </p>
                    <p className="text-xs text-ink-400">
                      wants you as their caregiver
                    </p>
                  </div>
                  <ChevronRight
                    size={16}
                    className="shrink-0 text-ink-400"
                    aria-hidden="true"
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <Modal
        open={selectedRequest !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen && !responding) setSelectedRequest(null);
        }}
      >
        {selectedRequest && (
          <ModalContent
            title="Caregiver request"
            description={`${selectedRequest.name} wants to give you access to their medical records.`}
          >
            <div className="flex items-center gap-3 rounded-xl border border-ink-400/10 p-3">
              <Avatar name={selectedRequest.name} size="lg" />
              <dl className="min-w-0 flex-1 space-y-0.5 text-sm">
                <div className="flex gap-2">
                  <dt className="text-ink-400">Name</dt>
                  <dd className="truncate font-medium text-ink-900">
                    {selectedRequest.name}
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-ink-400">Phone</dt>
                  <dd className="text-ink-900">{selectedRequest.phone}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-ink-400">Sent</dt>
                  <dd className="text-ink-900">
                    {formatDate(selectedRequest.since)}
                  </dd>
                </div>
              </dl>
            </div>

            <p className="mt-4 text-xs font-medium uppercase tracking-wide text-ink-400">
              You'll be able to see
            </p>
            {sharedCategories.length > 0 ? (
              <ul className="mt-2 space-y-1.5">
                {sharedCategories.map((permission) => (
                  <li
                    key={permission.category}
                    className="flex items-center gap-2 text-sm text-ink-900"
                  >
                    <Check
                      size={16}
                      className="shrink-0 text-primary-600"
                      aria-hidden="true"
                    />
                    {CATEGORY_LABELS[permission.category]}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-ink-400">No categories shared</p>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <Button
                variant="ghost"
                isLoading={responding === 'decline'}
                disabled={responding !== null}
                onClick={() => handleRespond(false)}
              >
                <X size={16} aria-hidden="true" />
                Decline
              </Button>
              <Button
                variant="primary"
                isLoading={responding === 'accept'}
                disabled={responding !== null}
                onClick={() => handleRespond(true)}
              >
                <Check size={16} aria-hidden="true" />
                Accept
              </Button>
            </div>
          </ModalContent>
        )}
      </Modal>
    </div>
  );
}
