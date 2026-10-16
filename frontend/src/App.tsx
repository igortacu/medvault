// import { Dialog } from '@radix-ui/react-dialog';

import { Navigate, Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import { RecipientBanner } from './features/Recipients/RecipientBanner';
import { useDatasetStore } from './store/datasetStore.ts';
import { useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { IdleTimeout } from './features/auth/IdleTimeout.tsx';
function App() {
  const loadDataset = useDatasetStore((state) => state.loadDataset);
  const isViewingRecipient = useDatasetStore(
    (state) => state.activeRecipient !== null
  );
  const needsLogin = useDatasetStore((state) => state.needsLogin);
  const hasUser = useDatasetStore((state) => state.currentUser !== null);
  const loadError = useDatasetStore((state) => state.error);

  useEffect(() => {
    loadDataset();
  }, [loadDataset]);

  // Swaps the primary palette (see index.css) while in a recipient's vault.
  useEffect(() => {
    const root = document.documentElement;
    if (isViewingRecipient) root.dataset.view = 'recipient';
    else delete root.dataset.view;
  }, [isViewingRecipient]);

  if (needsLogin) return <Navigate to="/welcome" replace />;
  // Nothing of the app shows until the session check says who is signed in.
  if (!hasUser && !loadError)
    return (
      <div className="flex min-h-screen items-center justify-center bg-primary-50/40">
        <Loader2
          className="h-6 w-6 animate-spin text-primary-600"
          aria-label="Loading"
        />
      </div>
    );
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
