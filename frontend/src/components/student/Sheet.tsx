import type { ElementType, ReactNode } from 'react'

import { cn } from '@/lib/utils'

const PADDING = { none: '', sm: 'p-4', md: 'p-5 sm:p-6', lg: 'p-6 sm:p-8' } as const

interface SheetProps {
  /** Depth tier: 1 resting, 2 raised (default), 3 hero. */
  depth?: 1 | 2 | 3
  padding?: keyof typeof PADDING
  /** Element to render: section, article, li, div... */
  as?: ElementType
  /** Lifts to the next tier on hover (only for sheets that are actually interactive). */
  lift?: boolean
  className?: string
  children?: ReactNode
}

/** Editorial surface with three shadow tiers; replaces the flat default card in the student portal. */
export function Sheet({ depth = 2, padding = 'md', as: Component = 'div', lift = false, className, children }: SheetProps) {
  return (
    <Component className={cn('sp-sheet', `sp-sheet-${depth}`, lift ? 'sp-sheet--lift' : undefined, PADDING[padding], className)}>
      {children}
    </Component>
  )
}
