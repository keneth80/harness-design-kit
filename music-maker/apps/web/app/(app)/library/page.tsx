import { LibraryGrid } from '@/components/library/library-grid';

export default function LibraryPage() {
  return (
    <div className="container mx-auto space-y-6 p-6">
      <h1 className="text-display-md">📚 Library</h1>
      <p className="text-body-md text-muted-foreground">
        생성한 모든 트랙을 모아보세요.
      </p>
      <LibraryGrid />
    </div>
  );
}
