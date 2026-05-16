'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    // mock sign-in — 추후 next-auth credentials provider 연결
    await new Promise((r) => setTimeout(r, 300));
    router.push('/dashboard');
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardContent className="space-y-4 p-6">
          <h1 className="text-heading-lg">로그인</h1>
          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <Label htmlFor="email">이메일</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="email-input"
              />
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? '로그인 중…' : '계속'}
            </Button>
          </form>
          <p className="text-center text-body-sm text-muted-foreground">
            계정이 없나요?{' '}
            <Link href="/sign-up" className="text-accent hover:underline">
              가입
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
