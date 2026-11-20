import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface EyebrowProps {
  /** Optional lucide icon shown before the label, in place of the violet bar. */
  icon?: ReactNode
  className?: string
  children: ReactNode
}

/** Small uppercase label above a title: violet bar (or icon) + 12px / 800 / .16em caps. */
export function Eyebrow({ icon, className, children }: EyebrowProps) {
  return (
    <span className={cn('sp-eyebrow', icon ? 'sp-eyebrow--plain' : undefined, className)}>
      {icon ? <span aria-hidden="true" className="inline-flex size-5 items-center justify-center [&>svg]:size-5">{icon}</span> : null}
      {children}
    </span>
  )
}
