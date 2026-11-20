import { Clock, Send } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface SubmitBarProps {
  /** "Solicitud pendiente" / "Solicitud nueva". */
  state: string
  /** "M-01 · Mañana · 1 recursado". */
  summary: string
  /** Formatted total, e.g. "9.200 Bs". */
  total: string
  /** Why the form cannot be sent yet, in the student's words; null when it can. */
  problem: string | null
  loading: boolean
  label: string
}

/** Sticky glass bar: what is being sent, the total and the submit button. Sits above the mobile tab bar and is safe-area aware. */
export function SubmitBar({ state, summary, total, problem, loading, label }: SubmitBarProps) {
  return (
    <div className="rm-sbar sp-glass-sheet" role="region" aria-label="Enviar solicitud">
      <div className="rm-sbar-state">
        <b><Clock aria-hidden="true" />{state}</b>
        <span>{problem ?? summary}</span>
      </div>
      <div className="rm-sbar-total">
        <small>Total</small>
        <b>{total}</b>
      </div>
      <Button type="submit" size="lg" className="rm-sbar-button active:scale-95 motion-reduce:active:scale-100" loading={loading} disabled={problem !== null}>
        <Send aria-hidden="true" />{label}
      </Button>
    </div>
  )
}
