// import { Dialog } from '@radix-ui/react-dialog';

import { Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import { useDatasetStore } from './store/datasetStore.ts';
import { useEffect } from 'react';
function App() {
  const loadDataset = useDatasetStore((state) => state.loadDataset);

  useEffect(() => {
    loadDataset('user-005');
  }, [loadDataset]);
  return (
    <div className="min-h-screen bg-primary-50/40">
      <Sidebar />
      <main id="main-content" className="min-w-0 lg:pl-64">
        <Outlet />
      </main>
    </div>
  );
}

export default App;
