import { NavLink } from 'react-router-dom';
import {
  Activity,
  Pill,
  FileCheck2,
  FlaskConical,
  UserCircle2,
  Users,
} from 'lucide-react';

const links = [
  { to: '/documents', label: 'Diagnostics', icon: Activity },
  { to: '/documents/prescriptions', label: 'Prescriptions', icon: Pill },
  { to: '/documents/certificates', label: 'Certificates', icon: FileCheck2 },
  {
    to: '/documents/other_medications',
    label: 'Other Medications',
    icon: FlaskConical,
  },
  { to: '/recipients', label: 'Recipients', icon: Users },
  { to: '/profile', label: 'Profile', icon: UserCircle2 },
];

function Sidebar() {
  return (
    <aside className="w-64 h-screen flex flex-col bg-primary-600 text-white">
      <div className="px-6 py-6 border-b border-white/10">
        <span className="font-display text-lg font-semibold tracking-tight">
          Medvault
        </span>
      </div>

      <nav className="flex flex-col gap-1 p-4">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/documents'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-card px-4 py-2.5 text-sm font-medium font-sans transition-colors ${
                isActive
                  ? 'bg-white text-primary-600 shadow-card'
                  : 'text-primary-50 hover:bg-primary-500/60 hover:text-white'
              }`
            }
          >
            <Icon size={18} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
