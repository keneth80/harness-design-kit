import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils/cn';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-3 py-1 text-body-sm font-medium transition-colors',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-accent/20 text-accent hover:bg-accent/30',
        outline: 'border-border text-foreground',
        success:
          'border-transparent bg-success/20 text-success',
        warning:
          'border-transparent bg-warning/20 text-warning',
        danger:
          'border-transparent bg-danger/20 text-danger',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
