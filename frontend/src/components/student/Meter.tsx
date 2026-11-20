import { motion, useReducedMotion } from 'motion/react'
import type { CSSProperties } from 'react'

import { cn } from '@/lib/utils'
import { meterPercent, meterSegments } from './student-editorial'

interface MeterProps {
  value: number
  max?: number
  /** Accessible name, e.g. "Cupos ocupados". */
  label: string
  tone?: 'default' | 'ok' | 'warn' | 'bad'
  /** Renders a segmented bar (one segment per seat when equal to `max`). */
  segments?: boolean | number
  /** Text for assistive tech, e.g. "12 de 40 cupos". Defaults to "value de max". */
  valueText?: string
  className?: string
}

/** Horizontal meter / seats bar with role="meter". Reduced motion shows the final fill without growing. */
export function Meter({ value, max = 100, label, tone = 'default', segments, valueText, className }: MeterProps) {
  const reduceMotion = useReducedMotion()
  const percent = meterPercent(value, max)
  const common = {
    role: 'meter',
    'aria-label': label,
    'aria-valuemin': 0,
    'aria-valuemax': max,
    'aria-valuenow': Math.min(Math.max(value, 0), max),
    'aria-valuetext': valueText ?? `${value} de ${max}`,
    'data-tone': tone,
  } as const

  if (segments) {
    const { filled, total } = meterSegments(value, max, typeof segments === 'number' ? segments : max)
    return (
      <div {...common} className={cn('sp-seats', className)}>
        {Array.from({ length: total }, (_, index) => (
          <span key={index} aria-hidden="true" className="sp-seg" data-filled={index < filled} style={{ '--sp-i': index } as CSSProperties} />
        ))}
      </div>
    )
  }

  return (
    <div {...common} className={cn('sp-meter', className)}>
      <motion.div
        aria-hidden="true"
        className="sp-meter-fill"
        style={{ width: `${percent}%` }}
        initial={{ scaleX: reduceMotion ? 1 : 0 }}
        animate={{ scaleX: 1 }}
        transition={reduceMotion ? { duration: 0 } : { duration: 1, ease: [0.22, 1, 0.36, 1] }}
      />
    </div>
  )
}
