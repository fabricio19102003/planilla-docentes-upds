import type { ReactNode } from 'react'

import { DisplayFigure, Eyebrow, InfoTip, Sheet } from '@/components/student'
import { formatBs, type Eligibility } from '@/lib/reenrollmentState'
import type { estimateAmounts } from '@/lib/studentPortalState'
import { RECURSADO_CHARGED_MAX } from './reenrollment-view'

interface SummarySheetProps {
  title: string
  /** Closing line under the receipt when more recursado subjects are chosen than are charged. */
  limitNote: string | null
  /** The printable receipt. */
  children: ReactNode
  amounts: ReturnType<typeof estimateAmounts>
  eligibility: Pick<Eligibility, 'recursado' | 'recursado_fee'>
}

/** Summary sheet: cuota and recursado lines with their rules in tips, the total as a display figure, and the printable receipt. */
export function SummarySheet({ title, limitNote, children, amounts, eligibility }: SummarySheetProps) {
  const perSubject = eligibility.recursado_fee.per_subject ?? 0
  const total = amounts.cuotasTotal + amounts.recursadoTotal
  return (
    <Sheet depth={3} padding="md" className="rm-summary">
      <Eyebrow>Comprobante · informativo</Eyebrow>
      <h2 className="rm-summary-title">{title}</h2>
      <ul className="rm-lines">
        {amounts.cuotas > 0 && (
          <li>
            <span className="rm-line-label">
              {amounts.cuotas} cuotas × {formatBs(amounts.cuota)}
              <InfoTip label="Cómo se calcula la cuota"
                content={`Tu cuota depende de tu beca (${amounts.scholarshipLabel}). El total de cuotas es ${formatBs(amounts.cuotasTotal)} y se paga en caja.`} />
            </span>
            <b>{formatBs(amounts.cuotasTotal)}</b>
          </li>
        )}
        {eligibility.recursado.length > 0 && (
          <li>
            <span className="rm-line-label">
              Recursado ({amounts.recursadoChosen})
              <InfoTip label="Cómo se cobra el recursado"
                content={`Cada materia recursada cuesta ${formatBs(perSubject)}. Se cobran como máximo ${RECURSADO_CHARGED_MAX} materias.`} />
            </span>
            <b>{formatBs(amounts.recursadoTotal)}</b>
          </li>
        )}
      </ul>
      <div className="rm-total" aria-live="polite">
        <span className="rm-total-label">Total a pagar en caja</span>
        <DisplayFigure value={total} prefix="Bs" size="lg" className="rm-total-figure" />
      </div>
      {children}
      {limitNote && <p className="rm-limit">{limitNote}</p>}
    </Sheet>
  )
}
