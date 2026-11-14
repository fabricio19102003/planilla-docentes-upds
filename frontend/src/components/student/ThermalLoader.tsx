import type { CSSProperties } from 'react'

import { cn } from '@/lib/utils'

interface ThermalLoaderProps {
  /** Text read by screen readers while the receipt prints. */
  label?: string
  /** Base font size in px (12-24). */
  size?: number
  /** Animation speed multiplier (0.5-2). */
  speed?: number
  className?: string
}

// Width of each printed line, in the order of the reference receipt.
const LINES = ['52%', '68%', '44%', '60%'] as const

/** R3 · Thermal receipt printer loader: a receipt feeds out in short jerks and is torn off. */
export function ThermalLoader({ label = 'Enviando tu solicitud', size = 16, speed = 1, className }: ThermalLoaderProps) {
  const style = { '--s': `${size}px`, '--k': speed } as CSSProperties
  return (
    <div className={cn('sp-printer', className)} role="status" style={style}>
      <span className="sp-printer-sr">{label}</span>
      <div className="sp-printer-body" aria-hidden="true">
        <i className="sp-printer-led" />
        <i className="sp-printer-slot" />
      </div>
      <div className="sp-printer-window" aria-hidden="true">
        <div className="sp-printer-paper">
          <i className="sp-printer-head" />
          {LINES.map((width) => (
            <b key={width} style={{ '--w': width } as CSSProperties} />
          ))}
          <i className="sp-printer-rule" />
          <b className="sp-printer-total" style={{ '--w': '38%' } as CSSProperties} />
          <i className="sp-printer-barcode" />
        </div>
      </div>
    </div>
  )
}
