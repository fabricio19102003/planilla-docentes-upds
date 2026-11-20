import type { ReactNode } from 'react'

import { Logo } from '@/components/layout/Logo'
import { cn } from '@/lib/utils'
import { Eyebrow } from '../Eyebrow'

interface AccessCardProps {
  /** Lucide icon in the tile above the title. */
  icon: ReactNode
  eyebrow: string
  title: ReactNode
  lead: ReactNode
  /** Plays the shake once the form was rejected (no movement under reduced motion). */
  shake?: boolean
  className?: string
  children: ReactNode
}

/** Glass sheet of the student access pages: logo, tile, eyebrow, 900-weight title and lead over the brand background. */
export function AccessCard({ icon, eyebrow, title, lead, shake = false, className, children }: AccessCardProps) {
  return (
    <>
      <div className="sa-logo">
        <Logo />
      </div>
      <section className={cn('sa-card sp-glass-sheet', className)} data-shake={shake}>
        <span aria-hidden="true" className="sa-tile">{icon}</span>
        <header className="sa-head">
          <Eyebrow>{eyebrow}</Eyebrow>
          <h1 className="sa-title">{title}</h1>
          <p className="sa-lead">{lead}</p>
        </header>
        {children}
      </section>
    </>
  )
}
