import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <header className="sticky top-0 z-40 flex h-14 items-center border-b border-border bg-canvas/80 px-4 backdrop-blur">
        <Link
          href="/"
          className="flex items-center gap-2 text-heading-md font-bold"
        >
          <span className="text-accent" aria-hidden>
            ♪
          </span>
          Music Maker
        </Link>
        <nav className="ml-auto flex items-center gap-2">
          <Link href="/sign-in">
            <Button variant="ghost" size="sm">
              로그인
            </Button>
          </Link>
          <Link href="/sign-up">
            <Button size="sm">시작하기</Button>
          </Link>
        </nav>
      </header>
      {children}
    </>
  );
}
