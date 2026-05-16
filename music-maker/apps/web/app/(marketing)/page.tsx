import Link from 'next/link';
import { Sparkles, Mic2, Music2, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function LandingPage() {
  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="container mx-auto flex flex-col items-center px-4 py-24 text-center">
        <span className="mb-4 inline-flex items-center gap-2 rounded-full bg-accent/20 px-3 py-1 text-body-sm text-accent">
          <Sparkles className="h-3 w-3" aria-hidden /> Powered by Mureka AI
        </span>
        <h1 className="text-display-md md:text-display-lg">
          30초 만에 저작권 걱정 없는 BGM 한 곡
        </h1>
        <p className="mt-6 max-w-2xl text-body-lg text-muted-foreground">
          텍스트만 쓰면, AI가 작곡·작사·보컬까지 끝냅니다. <br />
          YouTube 크리에이터, 팟캐스터, 인디 게임 개발자를 위한 음원 스튜디오.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link href="/sign-up">
            <Button size="lg" className="btn-ripple">
              <Sparkles className="h-5 w-5" aria-hidden /> 무료로 시작 (3
              크레딧)
            </Button>
          </Link>
          <Link href="/dashboard">
            <Button size="lg" variant="outline">
              데모 30초 듣기
            </Button>
          </Link>
        </div>
      </section>

      {/* Feature grid */}
      <section className="container mx-auto grid grid-cols-1 gap-6 px-4 py-12 md:grid-cols-3">
        <FeatureCard
          icon={<Zap className="h-6 w-6 text-accent" aria-hidden />}
          title="45초 P95"
          desc="Suno/Udio 평균 60-90초 대비 우위. 영상 편집 흐름을 끊지 않습니다."
        />
        <FeatureCard
          icon={<Mic2 className="h-6 w-6 text-accent" aria-hidden />}
          title="가사 → 보컬 → 반주"
          desc="단일 워크플로우. 한국어 가사 자동 생성 최적화."
        />
        <FeatureCard
          icon={<Music2 className="h-6 w-6 text-accent" aria-hidden />}
          title="스템 분리 다운로드"
          desc="보컬/드럼/베이스/멜로디 4트랙. 영상·게임에서 재믹스."
        />
      </section>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-6">
      <div className="mb-3">{icon}</div>
      <h3 className="text-heading-md">{title}</h3>
      <p className="mt-2 text-body-md text-muted-foreground">{desc}</p>
    </div>
  );
}
