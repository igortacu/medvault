import { useEffect, useState } from 'react';
import { Bell } from 'lucide-react';
import { useDatasetStore } from '../store/datasetStore';
import { useCaregiverStore } from '../store/caregiverStore';
import { IconButton } from './IconButton';
import { Button } from './Button';
import { Avatar } from './Avatar';
import { useToast } from './Toast';
import { cn } from '../lib/cn';

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
  const [respondingLinkId, setRespondingLinkId] = useState<string | null>(
    null
  );

  useEffect(() => {
    if (currentUser) loadUsersICareFor(currentUser.id);
  }, [currentUser, loadUsersICareFor]);

  const pendingRequests = usersICareFor.filter((r) => r.status === 'pending');

  async function handleRespond(linkId: string, accept: boolean) {
    setRespondingLinkId(linkId);
    try {
      await respondToCaregiverRequest({ linkId, accept });
      showToast({
        variant: 'success',
        title: accept ? 'Request accepted' : 'Request declined',
      });
    } catch {
      showToast({
        variant: 'error',
        title: 'Failed to respond',
        description: 'Please try again.',
      });
    } finally {
      setRespondingLinkId(null);
    }
  }

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
            <div className="mt-3 space-y-3">
              {pendingRequests.map((request) => (
                <div
                  key={request.linkId}
                  className="flex items-center gap-3 rounded-xl border border-ink-400/10 p-3"
                >
                  <Avatar name={request.name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-900">
                      {request.name}
                    </p>
                    <p className="text-xs text-ink-400">
                      wants to be your caregiver
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    <Button
                      size="sm"
                      variant="ghost"
                      isLoading={respondingLinkId === request.linkId}
                      onClick={() => handleRespond(request.linkId, false)}
                    >
                      Decline
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      isLoading={respondingLinkId === request.linkId}
                      onClick={() => handleRespond(request.linkId, true)}
                    >
                      Accept
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
