import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { clampPercent, ringCircumference, ringDashOffset } from './student-editorial'

interface ProgressRingProps {
  /** 0-100. */
  value: number
  /** Diameter in px. */
  size?: number
  stroke?: number
  /** Accessible description, e.g. "Avance de la carrera". */
  label: string
  /** Centre content; defaults to the percentage. */
  children?: ReactNode
  className?: string
}

/** Circular progress that draws itself on mount; with reduced motion it starts at the final offset. */
export function ProgressRing({ value, size = 120, stroke = 9, label, children, className }: ProgressRingProps) {
  const reduceMotion = useReducedMotion()
  const percent = clampPercent(value)
  const length = ringCircumference(size, stroke)
  const offset = ringDashOffset(percent, length)
  const center = size / 2

  return (
    <div
      role="img"
      aria-label={`${label}: ${Math.round(percent)}%`}
      className={cn('sp-ring', className)}
      style={{ width: size, height: size }}
    >
      <svg viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
        <circle className="sp-ring-track" cx={center} cy={center} r={(size - stroke) / 2} strokeWidth={stroke} />
        <motion.circle
          className="sp-ring-value"
          cx={center}
          cy={center}
          r={(size - stroke) / 2}
          strokeWidth={stroke}
          strokeDasharray={length}
          initial={{ strokeDashoffset: reduceMotion ? offset : length }}
          animate={{ strokeDashoffset: offset }}
          transition={reduceMotion ? { duration: 0 } : { duration: 1.3, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div aria-hidden="true" className="sp-ring-center" style={{ fontSize: size * 0.25 }}>
        {children ?? `${Math.round(percent)}%`}
      </div>
    </div>
  )
}
