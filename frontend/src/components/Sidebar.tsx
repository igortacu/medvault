import { NavLink } from 'react-router-dom';

function Sidebar() {
  return (
    <aside className="w-64 border-r">
      <nav className="flex flex-row gap-2 p-4">
        <NavLink to="/data">Diagnostics</NavLink>

        <NavLink to="/data/prescriptions">Prescriptions</NavLink>

        <NavLink to="/data/certificates">Certificates</NavLink>

        <NavLink to="/data/other_medications">Other Medications</NavLink>
        <NavLink to="/profile">Profile</NavLink>
        <NavLink to="/recipients">Recipients</NavLink>
      </nav>
    </aside>
  );
}

export default Sidebar;
