import type { ElementType, ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { Eyebrow } from './Eyebrow'

interface SectionHeaderProps {
  eyebrow?: string
  eyebrowIcon?: ReactNode
  title: ReactNode
  description?: ReactNode
  /** Heading element: h1 for the page title, h2 for a section. */
  as?: ElementType
  /** Content aligned to the right of the title (a badge, a link). */
  actions?: ReactNode
  /** Draws the short violet rule under the description. */
  rule?: boolean
  className?: string
}

/** Eyebrow + 900-weight display title + optional description + violet rule, as in the editorial page heads. */
export function SectionHeader({ eyebrow, eyebrowIcon, title, description, as: Heading = 'h2', actions, rule = true, className }: SectionHeaderProps) {
  return (
    <header className={cn('flex flex-wrap items-end justify-between gap-x-8 gap-y-4', className)}>
      <div className="grid min-w-0 gap-3">
        {eyebrow ? <Eyebrow icon={eyebrowIcon}>{eyebrow}</Eyebrow> : null}
        <Heading className="sp-display">{title}</Heading>
        {description ? <p className="sp-lead">{description}</p> : null}
        {rule ? <hr aria-hidden="true" className="sp-rule mt-1" /> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </header>
  )
}
