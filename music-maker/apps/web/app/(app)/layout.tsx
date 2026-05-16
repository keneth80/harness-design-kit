import { NavBar } from '@/components/layout/nav-bar';
import { SideNav } from '@/components/layout/side-nav';
import { BottomNav } from '@/components/layout/bottom-nav';

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <NavBar />
      <div className="flex flex-1">
        <SideNav />
        <main className="flex-1 overflow-x-hidden pb-20 md:pb-0">
          {children}
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
