import * as Dialog from '@radix-ui/react-dialog';
import { useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  Activity,
  ChevronRight,
  Menu,
  Pill,
  FileCheck2,
  FlaskConical,
  Hospital,
  Users,
  X,
} from 'lucide-react';
import { Avatar } from './Avatar';
import { IconButton } from './IconButton';

const links = [
  { to: '/documents', label: 'Diagnostics', icon: Activity },
  { to: '/documents/prescriptions', label: 'Prescriptions', icon: Pill },
  { to: '/documents/certificates', label: 'Certificates', icon: FileCheck2 },
  {
    to: '/documents/other_medications',
    label: 'Other medical information',
    icon: FlaskConical,
  },
  { to: '/institutions', label: 'Institutions', icon: Hospital },

  { to: '/recipients', label: 'Recipients', icon: Users },
];

function Sidebar() {
  const [openLocationKey, setOpenLocationKey] = useState<string | null>(null);
  const location = useLocation();
  const open = openLocationKey === location.key;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) =>
        setOpenLocationKey(nextOpen ? location.key : null)
      }
    >
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col bg-primary-600 text-white lg:flex">
        <div className="border-b border-white/10 px-6 py-6">
          <Link
            to="/documents"
            className="font-display text-lg font-semibold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-primary-600"
          >
            Medvault
          </Link>
        </div>

        <nav aria-label="Main navigation" className="flex flex-col gap-1 p-4">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/documents'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-card px-4 py-2.5 text-sm font-medium font-sans transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${
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

        <NavLink
          to="/profile"
          className={({ isActive }) =>
            `mt-auto flex items-center gap-3 border-t border-white/10 px-6 py-5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${
              isActive
                ? 'bg-primary-700/60 text-white'
                : 'text-primary-50 hover:bg-primary-500/60 hover:text-white'
            }`
          }
        >
          <Avatar name="Elena Popescu" size="sm" />
          <span className="truncate">Elena Popescu</span>
        </NavLink>
      </aside>

      <header className="sticky top-0 z-30 border-b border-primary-100/80 bg-white/95 text-ink-900 shadow-sm backdrop-blur lg:hidden">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
          <div className="flex min-w-0 items-center gap-3">
            <Dialog.Trigger asChild>
              <IconButton
                icon={<Menu size={21} strokeWidth={2.25} />}
                aria-label="Open navigation menu"
                className="text-primary-600 hover:bg-primary-50 focus-visible:ring-primary-500"
              />
            </Dialog.Trigger>

            <Link
              to="/documents"
              className="font-display text-lg font-semibold tracking-tight text-primary-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2"
            >
              Medvault
            </Link>
          </div>

          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `flex min-w-0 items-center gap-2 rounded-pill p-1 pr-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 ${
                isActive ? 'bg-primary-50' : 'hover:bg-primary-50'
              }`
            }
          >
            <Avatar name="Elena Popescu" size="sm" />
            <span className="hidden truncate text-sm font-medium text-ink-900 sm:block">
              Elena Popescu
            </span>
            <span className="sr-only">Open profile</span>
          </NavLink>
        </div>
      </header>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-primary-900/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-[min(20rem,calc(100vw-1.5rem))] flex-col bg-primary-600 text-white shadow-2xl focus:outline-none">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-5">
            <Dialog.Title className="font-display text-lg font-semibold tracking-tight">
              Medvault
            </Dialog.Title>
            <Dialog.Close asChild>
              <IconButton
                icon={<X size={20} strokeWidth={2.25} />}
                aria-label="Close navigation menu"
                className="text-white hover:bg-white/10 focus-visible:ring-white"
              />
            </Dialog.Close>
          </div>

          <Dialog.Description className="px-5 pb-2 pt-5 text-sm text-primary-100">
            Navigate your medical records and account.
          </Dialog.Description>

          <nav aria-label="Main navigation" className="flex flex-col gap-1 p-4">
            {links.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/documents'}
                onClick={() => setOpenLocationKey(null)}
                className={({ isActive }) =>
                  `flex items-center justify-between gap-3 rounded-card px-4 py-3 text-sm font-medium font-sans transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white ${
                    isActive
                      ? 'bg-white text-primary-600 shadow-card'
                      : 'text-primary-50 hover:bg-primary-500/60 hover:text-white'
                  }`
                }
              >
                <span className="flex items-center gap-3">
                  <Icon size={18} strokeWidth={2} />
                  {label}
                </span>
                <ChevronRight size={16} aria-hidden="true" />
              </NavLink>
            ))}
          </nav>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default Sidebar;
