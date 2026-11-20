import { ArrowRight, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface LinkButtonProps {
  to: string
  /** Icon after the label; the arrow nudges forward on hover and focus. */
  icon?: LucideIcon
  /** primary: filled call to action; link: ruled text link; light: link on the ink sheet. */
  variant?: 'primary' | 'link' | 'light'
  className?: string
  children: ReactNode
}

/** Router link drawn as an editorial button: 44px target, icon, press and hover feedback. */
export function LinkButton({ to, icon: Icon = ArrowRight, variant = 'link', className, children }: LinkButtonProps) {
  return (
    <Link to={to} className={cn('sph-link', `sph-link--${variant}`, className)}>
      {children}
      <Icon aria-hidden="true" className="sph-nudge" />
    </Link>
  )
}
