'use client';

import * as React from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { LyricsEditor } from '@/components/studio/lyrics-editor';

export default function LyricsPage() {
  const [lyrics, setLyrics] = React.useState('');

  return (
    <div className="container mx-auto p-4">
      <header className="mb-4 flex items-center gap-2">
        <Link href="/studio">
          <Button variant="ghost" size="sm">
            ← 뒤로
          </Button>
        </Link>
        <h1 className="text-display-md">가사 에디터</h1>
      </header>

      <Card>
        <CardContent className="p-4">
          <LyricsEditor value={lyrics} onChange={setLyrics} />
        </CardContent>
      </Card>

      <div className="mt-4 flex justify-end">
        <Button>이 가사로 노래 생성 →</Button>
      </div>
    </div>
  );
}
