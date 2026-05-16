import { StudioPanel } from '@/components/studio/studio-panel';
import { Card, CardContent } from '@/components/ui/card';

export default function StudioPage() {
  return (
    <div className="container mx-auto grid grid-cols-1 gap-4 p-4 xl:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <h1 className="text-display-md">Studio</h1>
        <StudioPanel />
      </div>

      <aside className="hidden xl:block" aria-label="히스토리">
        <Card>
          <CardContent className="p-4">
            <h2 className="mb-3 text-heading-md">History</h2>
            <p className="text-body-sm text-muted-foreground">
              최근 생성한 트랙이 여기에 표시됩니다.
            </p>
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}
