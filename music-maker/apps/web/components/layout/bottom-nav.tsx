'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Mic2, Library as LibIcon, User } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

const ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/studio', label: 'Studio', icon: Mic2 },
  { href: '/library', label: 'Library', icon: LibIcon },
  { href: '/settings', label: 'Profile', icon: User },
] as const;

/** 모바일용 하단 4탭 (md 이하). */
export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="하단 내비게이션"
      className="fixed bottom-0 left-0 right-0 z-30 flex h-16 items-center justify-around border-t border-border bg-surface md:hidden"
    >
      {ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname?.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex flex-col items-center gap-1 px-3 py-2 text-body-sm',
              active ? 'text-accent' : 'text-muted-foreground',
            )}
            aria-current={active ? 'page' : undefined}
          >
            <Icon className="h-5 w-5" aria-hidden />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
