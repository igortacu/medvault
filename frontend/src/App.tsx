// import { Dialog } from '@radix-ui/react-dialog';

import { Navigate, Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import { RecipientBanner } from './features/Recipients/RecipientBanner';
import { useDatasetStore } from './store/datasetStore.ts';
import { useEffect } from 'react';
import { IdleTimeout } from './features/auth/IdleTimeout.tsx';
import { hasKnownAccount } from './lib/knownAccount.ts';
function App() {
  const loadDataset = useDatasetStore((state) => state.loadDataset);
  const isViewingRecipient = useDatasetStore(
    (state) => state.activeRecipient !== null
  );
  const needsLogin = useDatasetStore((state) => state.needsLogin);

  useEffect(() => {
    loadDataset();
  }, [loadDataset]);

  // Swaps the primary palette (see index.css) while in a recipient's vault.
  useEffect(() => {
    const root = document.documentElement;
    if (isViewingRecipient) root.dataset.view = 'recipient';
    else delete root.dataset.view;
  }, [isViewingRecipient]);

  // First visit from this browser opens on registration; afterwards, sign-in.
  if (needsLogin)
    return <Navigate to={hasKnownAccount() ? '/login' : '/signup'} replace />;
  return (
    <div className="min-h-screen bg-primary-50/40">
      <IdleTimeout />
      <Sidebar />
      <main id="main-content" className="min-w-0 lg:pl-64">
        <RecipientBanner />
        <Outlet />
      </main>
    </div>
  );
}

export default App;
