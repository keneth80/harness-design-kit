import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Tailwind 클래스 병합 유틸 (shadcn 표준).
 * 충돌하는 클래스는 뒤쪽 값을 우선.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
