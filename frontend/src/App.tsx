// import { Dialog } from '@radix-ui/react-dialog';

import { Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';

function App() {
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
