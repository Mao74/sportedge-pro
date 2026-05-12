import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/cn';

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  rounded?: 'sm' | 'md' | 'lg' | 'full';
}

const RADIUS = {
  sm: 'rounded',
  md: 'rounded-md',
  lg: 'rounded-lg',
  full: 'rounded-full',
} as const;

export function Skeleton({
  className,
  width,
  height,
  rounded = 'md',
  style,
  ...rest
}: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse bg-bg-hover', RADIUS[rounded], className)}
      style={{ width, height, ...style }}
      {...rest}
    />
  );
}
