import { Outlet } from 'react-router-dom';

function Documents() {
  return (
    <main className="flex-1">
      <Outlet />
    </main>
  );
}

export default Documents;
