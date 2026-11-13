import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Printer } from 'lucide-react'
import { useReducedMotion } from 'motion/react'

import { cn } from '@/lib/utils'

export interface ReceiptItem {
  qty: number | string
  label: string
  amount: string
}

interface PrintReceiptProps {
  title?: string
  /** Lines under the title (office, date, semester...). */
  subtitle?: string[]
  items: ReceiptItem[]
  total: string
  totalLabel?: string
  /** Two small texts shown on one row under the total. */
  notes?: [string, string?]
  /** Closing line under the barcode. */
  footer?: string
  buttonLabel?: string
  /** Base font size in px (12-24). */
  size?: number
  /** Animation speed multiplier (0.5-2). */
  speed?: number
  className?: string
}

/** R2 · Printing receipt card: a thermal receipt feeds out of a printer; the button prints it again. */
export function PrintReceipt({
  title = 'UPDS COBIJA',
  subtitle = [],
  items,
  total,
  totalLabel = 'Total',
  notes,
  footer,
  buttonLabel = 'Imprimir comprobante',
  size = 16,
  speed = 1,
  className,
}: PrintReceiptProps) {
  const reduceMotion = useReducedMotion()
  const root = useRef<HTMLDivElement>(null)
  const ticket = useRef<HTMLDivElement>(null)
  const fallback = useRef<number | undefined>(undefined)
  const [announcement, setAnnouncement] = useState('')

  useEffect(() => () => window.clearTimeout(fallback.current), [])

  const finish = () => {
    window.clearTimeout(fallback.current)
    root.current?.classList.remove('pg')
    setAnnouncement('Comprobante impreso')
  }

  const print = () => {
    const el = root.current
    const paper = ticket.current
    if (!el || !paper) return
    setAnnouncement('')
    el.classList.remove('on', 'pg')
    void paper.offsetWidth
    el.classList.add('on', 'pg')
    window.clearTimeout(fallback.current)
    // Reduced motion prints at once; otherwise transitionend announces, with a timer as backup.
    fallback.current = window.setTimeout(finish, reduceMotion ? 0 : (2400 / speed) + 200)
  }

  const style = { '--s': `${size}px`, '--k': speed } as CSSProperties

  return (
    <div className={cn('sp-receipt-wrap', className)} style={style}>
      <div ref={root} className="sp-receipt on">
        <div className="sp-receipt-printer" aria-hidden="true">
          <i className="sp-receipt-led" />
          <i className="sp-receipt-slot" />
        </div>
        <div className="sp-receipt-paper">
          <div
            ref={ticket}
            className="sp-receipt-ticket"
            onTransitionEnd={(event) => {
              if (event.target === event.currentTarget && event.propertyName === 'transform') finish()
            }}
          >
            <p className="sp-receipt-head">
              <b>{title}</b>
              {subtitle.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </p>
            <ul>
              {items.map(({ qty, label, amount }) => (
                <li key={`${qty}-${label}`}>
                  <span>{qty}</span>
                  <span>{label}</span>
                  <span>{amount}</span>
                </li>
              ))}
            </ul>
            <p className="sp-receipt-total">
              <span>{totalLabel}</span>
              <b>{total}</b>
            </p>
            {notes && (
              <p className="sp-receipt-notes">
                <span>{notes[0]}</span>
                {notes[1] && <span>{notes[1]}</span>}
              </p>
            )}
            <i className="sp-receipt-barcode" aria-hidden="true" />
            {footer && <p className="sp-receipt-footer">{footer}</p>}
          </div>
        </div>
        <button type="button" className="sp-receipt-button" onClick={print}>
          <Printer aria-hidden="true" />
          {buttonLabel}
        </button>
      </div>
      <span className="sp-sr-only" role="status" aria-live="polite">
        {announcement}
      </span>
    </div>
  )
}
