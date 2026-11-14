import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface ClinicNotFoundProps {
  title?: string
  message?: string
  tag?: string
  ctaLabel?: string
  ctaTo?: string
  /** Fill the nearest positioned ancestor instead of the whole viewport. */
  contained?: boolean
  /** Animation speed multiplier (0.5-2). */
  speed?: number
  className?: string
}

const ECG =
  'M0 150 H40 q10 -16 20 0 H86 l6 10 l9 -126 l10 150 l7 -34 H150 q18 -30 36 0 H232 q10 -16 20 0 H278 l6 10 l9 -126 l10 150 l7 -34 H342 q16 -26 32 0 H414 L484 40 V260 V150 H556 V100 C556 26 652 26 652 100 V200 C652 274 556 274 556 200 V150 V200 C556 274 652 274 652 200 V150 H716 L786 40 V260 V150 H1200'

/** R4 · Clinic 404: a heart monitor line beats twice, draws a huge 404 and goes flat. */
export function ClinicNotFound({
  title = 'Esta página no tiene pulso.',
  message = 'Hicimos todos los estudios y no hay nada más que hacer. Vos, en cambio, estás de diez.',
  tag = 'URGENCIAS · DIAGNÓSTICO 404',
  ctaLabel = 'Volver a recepción',
  ctaTo = '/estudiante',
  contained = false,
  speed = 1,
  className,
}: ClinicNotFoundProps) {
  return (
    <div
      className={cn('sp-404', contained && 'sp-404--contained', className)}
      role="region"
      aria-label="Error 404"
      style={{ '--k': speed } as CSSProperties}
    >
      <div className="sp-404-copy">
        <svg className="sp-404-ecg" viewBox="0 0 1200 300" aria-hidden="true">
          <path className="sp-404-base" d={ECG} />
          <path className="sp-404-trail" pathLength="1000" d={ECG} />
          <path className="sp-404-beam" pathLength="1000" d={ECG} />
        </svg>
        <span className="sp-404-tag">{tag}</span>
        <h1 className="sp-404-title">{title}</h1>
        <p className="sp-404-sub">{message}</p>
        <Link className="sp-404-cta" to={ctaTo}>
          {ctaLabel}
        </Link>
      </div>
    </div>
  )
}
