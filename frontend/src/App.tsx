// import { Dialog } from '@radix-ui/react-dialog';

import { Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import { RecipientBanner } from './features/Recipients/RecipientBanner';
import { useDatasetStore } from './store/datasetStore.ts';
import { useEffect } from 'react';
function App() {
  const loadDataset = useDatasetStore((state) => state.loadDataset);
  const isViewingRecipient = useDatasetStore(
    (state) => state.activeRecipient !== null
  );

  useEffect(() => {
    loadDataset();
  }, [loadDataset]);

  // Swaps the primary palette (see index.css) while in a recipient's vault.
  useEffect(() => {
    const root = document.documentElement;
    if (isViewingRecipient) root.dataset.view = 'recipient';
    else delete root.dataset.view;
  }, [isViewingRecipient]);
  return (
    <div className="min-h-screen bg-primary-50/40">
      <Sidebar />
      <main id="main-content" className="min-w-0 lg:pl-64">
        <RecipientBanner />
        <Outlet />
      </main>
    </div>
  );
}

export default App;
