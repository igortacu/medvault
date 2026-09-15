// import { Dialog } from '@radix-ui/react-dialog';

import { Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import { useDatasetStore } from './store/datasetStore.ts';
import { useEffect } from 'react';
function App() {
  const loadDataset = useDatasetStore((state) => state.loadDataset);

  useEffect(() => {
    loadDataset('user-001');
  }, [loadDataset]);
  return (
    <>
      <div className="flex min-h-screen">
        <Sidebar />

        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </>
  );
}

export default App;
