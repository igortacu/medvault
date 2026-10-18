import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Building2, CheckCircle2, Plus } from 'lucide-react';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState } from '../../components/EmptyState';
import { SkeletonListItem } from '../../components/Skeleton';
import { useToast } from '../../components/Toast';
import { useDatasetStore } from '../../store/datasetStore';
import type { Institution as InstitutionRecord } from '../../api/types';
import Institution from './Institution';
import { ConnectForm } from './ConnectForm';
import { ConnectInstitutionModal } from './ConnectInstitutionModal';
import { CONSENT_TEXT_VERSION } from './consent';
import {
  connectable,
  latestConnections,
  resultMessage,
} from './connectionRules';

type ModalState =
  | { mode: 'add' }
  | { mode: 'reconnect'; institution: InstitutionRecord }
  | null;

function Institutions() {
  const institutions = useDatasetStore((state) => state.institutions);
  const connections = useDatasetStore((state) => state.institutionConnections);
  const isLoading = useDatasetStore((state) => state.isLoading);
  const connectPublicInstitutions = useDatasetStore(
    (state) => state.connectPublicInstitutions
  );
  const addInstitutionConnection = useDatasetStore(
    (state) => state.addInstitutionConnection
  );
  const revokeInstitutionConnection = useDatasetStore(
    (state) => state.revokeInstitutionConnection
  );
  const refreshInstitutionConnections = useDatasetStore(
    (state) => state.refreshInstitutionConnections
  );
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [isConnectingPublic, setIsConnectingPublic] = useState(false);
  const [isConnectingOne, setIsConnectingOne] = useState(false);
  const [modal, setModal] = useState<ModalState>(null);
  const [toDisconnect, setToDisconnect] = useState<InstitutionRecord | null>(
    null
  );
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  const latest = useMemo(() => latestConnections(connections), [connections]);
  const publicToConnect = connectable(institutions, latest, 'public');
  const privateToAdd = connectable(institutions, latest, 'private');
  const publicCount = institutions.filter((i) => i.type === 'public').length;
  const listed = institutions
    .filter((i) => latest.has(i.id))
    .sort((a, b) => a.name.localeCompare(b.name));

  // Landing back from the OAuth redirect: re-read the connections the
  // callback just wrote, report the outcome, then drop the query param.
  const result = searchParams.get('connection');
  const handledResult = useRef<string | null>(null);
  useEffect(() => {
    if (!result || institutions.length === 0) return;
    if (handledResult.current === result) return;
    handledResult.current = result;
    void (async () => {
      await refreshInstitutionConnections();
      const message = resultMessage(
        result,
        institutions,
        latestConnections(useDatasetStore.getState().institutionConnections)
      );
      if (message) showToast(message);
      setSearchParams({}, { replace: true });
    })();
  }, [
    result,
    institutions,
    refreshInstitutionConnections,
    setSearchParams,
    showToast,
  ]);

  // The real flow leaves for the institution's authorize page; the mock
  // returns a path back into the app.
  function goTo(url: string) {
    if (url.startsWith('/')) {
      handledResult.current = null;
      navigate(url);
    } else {
      window.location.assign(url);
    }
  }

  function connectFailed() {
    showToast({
      variant: 'error',
      title: "Couldn't start connecting",
      description: 'Please try again in a moment.',
    });
  }

  async function handleConnectPublic(idnp: string) {
    setIsConnectingPublic(true);
    const started = await connectPublicInstitutions(idnp, CONSENT_TEXT_VERSION);
    if (started?.authorizeUrl) {
      goTo(started.authorizeUrl);
      // Leaving the page; keep the button busy until then.
      if (started.authorizeUrl.startsWith('/')) setIsConnectingPublic(false);
      return;
    }
    setIsConnectingPublic(false);
    if (!started) {
      connectFailed();
      return;
    }
    // Nothing could be started: every attempt was recorded as failed.
    showToast({
      variant: 'error',
      title: "Couldn't reach the public institutions",
      description: 'See the list below and try again later.',
    });
  }

  async function handleConnectOne(institutionId: string, idnp: string) {
    setIsConnectingOne(true);
    const authorizeUrl = await addInstitutionConnection(
      institutionId,
      idnp,
      CONSENT_TEXT_VERSION
    );
    if (authorizeUrl) {
      setModal(null);
      goTo(authorizeUrl);
      if (authorizeUrl.startsWith('/')) setIsConnectingOne(false);
      return;
    }
    setIsConnectingOne(false);
    connectFailed();
  }

  async function handleDisconnect() {
    const connection = toDisconnect && latest.get(toDisconnect.id);
    if (!toDisconnect || !connection) return;
    setIsDisconnecting(true);
    await revokeInstitutionConnection(connection.id);
    setIsDisconnecting(false);
    // The store swallows errors into `error` rather than rethrowing.
    if (useDatasetStore.getState().error) {
      showToast({
        variant: 'error',
        title: "Couldn't disconnect",
        description: 'Please try again.',
      });
      return;
    }
    showToast({
      variant: 'success',
      title: `Disconnected from ${toDisconnect.name}`,
      description: 'Its records no longer appear in MedVault.',
    });
    setToDisconnect(null);
  }

  const isInitialLoad = isLoading && institutions.length === 0;

  return (
    <div className="px-4 py-6 sm:px-6 lg:px-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink-900">
            Institutions
          </h1>
          <p className="mt-1 text-sm text-ink-400">
            Connect hospitals and clinics to see their records about you in
            MedVault.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setModal({ mode: 'add' })}
          disabled={isInitialLoad || privateToAdd.length === 0}
        >
          <Plus size={16} />
          Add institution
        </Button>
      </div>

      {isInitialLoad ? (
        <div className="mt-6 space-y-3">
          <SkeletonListItem />
          <SkeletonListItem />
        </div>
      ) : (
        <>
          <section className="mt-6" aria-labelledby="public-heading">
            {publicToConnect.length > 0 ? (
              <Card>
                <h2
                  id="public-heading"
                  className="font-display text-base font-semibold text-ink-900"
                >
                  Connect public institutions
                </h2>
                <p className="mt-1 text-sm text-ink-600">
                  One consent connects every public hospital that has records
                  for you.
                </p>
                <div className="mt-4">
                  <ConnectForm
                    institutions={publicToConnect}
                    submitLabel="I consent, connect"
                    isSubmitting={isConnectingPublic}
                    onSubmit={handleConnectPublic}
                  />
                </div>
              </Card>
            ) : (
              publicCount > 0 && (
                <Card className="flex items-center gap-3">
                  <CheckCircle2
                    size={20}
                    className="shrink-0 text-primary-600"
                    aria-hidden
                  />
                  <p id="public-heading" className="text-sm text-ink-900">
                    All {publicCount} public institutions are connected.
                  </p>
                </Card>
              )
            )}
          </section>

          <section className="mt-8" aria-labelledby="connections-heading">
            <h2
              id="connections-heading"
              className="font-display text-base font-semibold text-ink-900"
            >
              Your institutions
            </h2>
            <div className="mt-3 space-y-3">
              {listed.length === 0 ? (
                <EmptyState
                  icon={<Building2 size={32} />}
                  title="No institutions yet"
                  description="Institutions you connect will appear here, with what they share and when."
                />
              ) : (
                listed.map((institution) => (
                  <Institution
                    key={institution.id}
                    institution={institution}
                    connection={latest.get(institution.id)!}
                    onReconnect={() =>
                      setModal({ mode: 'reconnect', institution })
                    }
                    onDisconnect={() => setToDisconnect(institution)}
                  />
                ))
              )}
            </div>
          </section>
        </>
      )}

      <ConnectInstitutionModal
        open={modal !== null}
        onOpenChange={(open) => !open && setModal(null)}
        mode={modal?.mode ?? 'add'}
        institutions={
          modal?.mode === 'reconnect' ? [modal.institution] : privateToAdd
        }
        isSubmitting={isConnectingOne}
        onConnect={handleConnectOne}
      />

      <ConfirmDialog
        open={toDisconnect !== null}
        onOpenChange={(open) => !open && setToDisconnect(null)}
        title={`Disconnect ${toDisconnect?.name ?? ''}?`}
        description="MedVault loses access straight away and its records disappear from your vault. You can connect it again later."
        confirmLabel="Disconnect"
        isLoading={isDisconnecting}
        onConfirm={handleDisconnect}
      />
    </div>
  );
}

export default Institutions;
