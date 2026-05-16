'use client';

import Link from 'next/link';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { CreditMeter } from '@/components/shared/credit-meter';

export function NavBar() {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-4 border-b border-border bg-canvas/80 px-4 backdrop-blur">
      <Link
        href="/dashboard"
        className="flex items-center gap-2 text-heading-md font-bold"
      >
        <span className="text-accent" aria-hidden>
          ♪
        </span>
        <span className="hidden sm:inline">Music Maker</span>
      </Link>

      <div className="relative ml-auto hidden max-w-sm flex-1 md:block">
        <Search
          className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          placeholder="검색…"
          aria-label="라이브러리 검색"
          className="pl-9"
        />
      </div>

      <CreditMeter />

      <button
        type="button"
        className="flex h-8 w-8 items-center justify-center rounded-full bg-elevated text-body-sm focus-ring"
        aria-label="사용자 메뉴"
      >
        유
      </button>
    </header>
  );
}
