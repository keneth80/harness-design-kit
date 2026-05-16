import type { Metadata } from 'next';
import './globals.css';
import { Providers } from '@/components/providers';

export const metadata: Metadata = {
  title: 'Music Maker — AI 음원 생성 스튜디오',
  description:
    '텍스트만 쓰면 45초 안에 보컬+반주 완성형 트랙. 저작권 걱정 없는 BGM, Mureka AI 기반.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-canvas text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
