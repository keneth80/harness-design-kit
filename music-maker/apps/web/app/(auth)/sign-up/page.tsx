'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';

export default function SignUpPage() {
  const router = useRouter();
  const [email, setEmail] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    await new Promise((r) => setTimeout(r, 300));
    router.push('/dashboard');
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardContent className="space-y-4 p-6">
          <h1 className="text-heading-lg">시작하기 (3 크레딧 무료)</h1>
          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <Label htmlFor="email">이메일</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? '가입 중…' : '계정 만들기'}
            </Button>
          </form>
          <p className="text-center text-body-sm text-muted-foreground">
            이미 가입했나요?{' '}
            <Link href="/sign-in" className="text-accent hover:underline">
              로그인
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
