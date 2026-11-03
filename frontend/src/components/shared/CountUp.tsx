import { useEffect, useState } from 'react'

import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { COUNT_UP_DURATION_MS, countUpFrame, countUpTarget } from '@/lib/countUp'

export interface CountUpProps {
  /** Number to animate to. Anything else (text such as "Sin datos") renders unchanged. */
  value: number | string | null | undefined
  /** Formats every frame, so currency and percent keep the same formatting as a static value. */
  format?: (value: number) => string
  durationMs?: number
}

const formatInteger = (value: number) => String(Math.round(value))

/**
 * Counts from 0 to `value` with an ease-out curve. Screen readers get the formatted final value
 * right away; the animated digits are hidden from them. With reduced motion the final value shows at once.
 */
export function CountUp({ value, format, durationMs = COUNT_UP_DURATION_MS }: CountUpProps) {
  const target = countUpTarget(value)
  const reducedMotion = useReducedMotion()
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    if (target == null || reducedMotion) return
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const elapsed = now - start
      setCurrent(countUpFrame(target, elapsed, durationMs))
      if (elapsed < durationMs) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, reducedMotion, durationMs])

  if (target == null) return <>{value}</>

  const formatValue = format ?? (Number.isInteger(target) ? formatInteger : String)
  const finalText = formatValue(target)
  if (reducedMotion) return <span className="tabular-nums">{finalText}</span>

  return (
    <span className="tabular-nums">
      <span className="sr-only">{finalText}</span>
      <span aria-hidden="true">{formatValue(current)}</span>
    </span>
  )
}
