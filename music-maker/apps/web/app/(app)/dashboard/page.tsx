import Link from 'next/link';
import { Sparkles, Library as LibIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export default function DashboardPage() {
  return (
    <div className="container mx-auto space-y-6 p-6">
      <h1 className="text-display-md">Dashboard</h1>
      <p className="text-body-lg text-muted-foreground">
        AI 음원 생성을 시작하거나 라이브러리를 둘러보세요.
      </p>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>새 곡 만들기</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-body-md text-muted-foreground">
              프롬프트 한 줄로 45초 안에 2개 트랙 생성.
            </p>
            <Link href="/studio">
              <Button>
                <Sparkles className="h-4 w-4" aria-hidden /> Studio로
              </Button>
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>내 라이브러리</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-body-md text-muted-foreground">
              생성한 트랙 모두 모아보기, 필터/태그/즐겨찾기.
            </p>
            <Link href="/library">
              <Button variant="outline">
                <LibIcon className="h-4 w-4" aria-hidden /> Library
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
