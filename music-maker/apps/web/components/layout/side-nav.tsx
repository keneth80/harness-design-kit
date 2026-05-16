'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Mic2,
  Library as LibIcon,
  FolderClosed,
  Settings,
  CreditCard,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils/cn';

const ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/studio', label: 'Studio', icon: Mic2 },
  { href: '/library', label: 'Library', icon: LibIcon },
  { href: '/projects', label: 'Projects', icon: FolderClosed },
] as const;

const FOOTER = [
  { href: '/settings', label: 'Settings', icon: Settings },
  { href: '/billing', label: 'Billing', icon: CreditCard },
] as const;

export function SideNav() {
  const pathname = usePathname();

  return (
    <aside
      className="hidden h-[calc(100vh-3.5rem)] w-56 shrink-0 flex-col gap-1 border-r border-border bg-surface p-3 md:flex"
      aria-label="주 내비게이션"
    >
      <Link
        href="/studio"
        className="mb-2 flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-body-md font-semibold text-white hover:bg-accent-hover"
      >
        <Plus className="h-4 w-4" aria-hidden /> New
      </Link>

      <nav className="flex flex-col gap-1">
        {ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-body-md transition-colors',
                active
                  ? 'bg-elevated text-foreground'
                  : 'text-muted-foreground hover:bg-elevated hover:text-foreground',
              )}
              aria-current={active ? 'page' : undefined}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>

      <hr className="my-2 border-border" />

      <nav className="flex flex-col gap-1">
        {FOOTER.map(({ href, label, icon: Icon }) => {
          const active = pathname?.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-body-md transition-colors',
                active
                  ? 'bg-elevated text-foreground'
                  : 'text-muted-foreground hover:bg-elevated hover:text-foreground',
              )}
              aria-current={active ? 'page' : undefined}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
