import { animate, useReducedMotion } from 'motion/react'
import { useLayoutEffect, useRef } from 'react'

import { cn } from '@/lib/utils'
import { formatFigure } from './student-editorial'

interface DisplayFigureProps {
  value: number
  /** Fixed decimals (es-BO decimal comma). */
  decimals?: number
  /** Currency or unit before the number, e.g. "Bs". */
  prefix?: string
  /** Unit after the number, e.g. "%". */
  suffix?: string
  size?: 'md' | 'lg' | 'xl' | 'base'
  /** Seconds of the count-up. */
  duration?: number
  className?: string
}

/** Big tabular figure that counts up to `value` (es-BO format). Reduced motion shows the final value immediately. */
export function DisplayFigure({ value, decimals = 0, prefix, suffix, size = 'base', duration = 0.9, className }: DisplayFigureProps) {
  const reduceMotion = useReducedMotion()
  const text = useRef<HTMLSpanElement>(null)
  const final = formatFigure(value, decimals)

  useLayoutEffect(() => {
    const node = text.current
    if (!node) return
    if (reduceMotion) {
      node.textContent = final
      return
    }
    node.textContent = formatFigure(0, decimals)
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (current) => {
        node.textContent = formatFigure(current, decimals)
      },
      onComplete: () => {
        node.textContent = final
      },
    })
    return () => controls.stop()
  }, [value, decimals, duration, final, reduceMotion])

  return (
    <span className={cn('sp-figure', className)} data-size={size === 'base' ? undefined : size}>
      {prefix ? (
        <span aria-hidden="true" className="sp-figure-prefix">
          {prefix}
        </span>
      ) : null}
      <span aria-hidden="true" ref={text}>
        {final}
      </span>
      {suffix ? (
        <span aria-hidden="true" className="sp-figure-suffix">
          {suffix}
        </span>
      ) : null}
      <span className="sp-sr-only">{`${prefix ? `${prefix} ` : ''}${final}${suffix ? ` ${suffix}` : ''}`}</span>
    </span>
  )
}
