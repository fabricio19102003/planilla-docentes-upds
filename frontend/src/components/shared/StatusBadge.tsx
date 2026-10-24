import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { TONE_DOT, type Tone } from './tones'

export interface StatusBadgeProps {
  /** Tone of the dot. Defaults to `neutral`. */
  tone?: Tone
  children: ReactNode
  className?: string
}

/**
 * Status indicator: an outline Badge with a colored dot (S11).
 * Tones: primary, success, warning, destructive, info, neutral.
 *
 * @example
 * <StatusBadge tone="success">Activo</StatusBadge>
 */
export function StatusBadge({ tone = 'neutral', children, className }: StatusBadgeProps) {
  return (
    <Badge variant="outline" className={cn('gap-1.5', className)}>
      <span aria-hidden="true" className={cn('size-1.5 shrink-0 rounded-full', TONE_DOT[tone])} />
      {children}
    </Badge>
  )
}
