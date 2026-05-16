'use client';

import { useParams } from 'next/navigation';

export default function TrackDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-display-md">Track 상세</h1>
      <p className="text-body-md text-muted-foreground">ID: {params?.id}</p>
      <p className="mt-4 text-body-md">
        (스텁) 트랙 상세 페이지 — 추후 wavesurfer + 메타데이터 + 다운로드 UI
        확장 예정.
      </p>
    </div>
  );
}
