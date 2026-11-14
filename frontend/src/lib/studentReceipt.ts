// Pure lines of the Rematrícula receipt (R2): the informative amounts the student sees before sending the request.

import { formatBs } from './reenrollmentState.ts'
import type { GroupChoices, StudentReenrollmentView } from './studentPortalState.ts'

// Same cap as estimateAmounts: only the first three recursado subjects are charged.
const RECURSADO_CHARGED_MAX = 3

export interface ReceiptLine {
  qty: number
  label: string
  amount: string
}

export interface StudentReceipt {
  title: string
  subtitle: string[]
  items: ReceiptLine[]
  total: string
  notes: [string, string]
  /** Shown next to the receipt when more recursado subjects are chosen than are charged. */
  limitNote: string | null
}

interface ReceiptInput {
  eligibility: StudentReenrollmentView['eligibility']
  choices: GroupChoices
  termCode?: string
  studentName?: string
  documentNumber?: string
}

export function buildReceipt({ eligibility, choices, termCode, studentName, documentNumber }: ReceiptInput): StudentReceipt {
  const { scholarship } = eligibility
  const perSubject = eligibility.recursado_fee.per_subject ?? 0
  const chosen = eligibility.recursado.filter((subject) => subject.code && choices[subject.code])
  const charged = Math.min(chosen.length, RECURSADO_CHARGED_MAX)

  const items: ReceiptLine[] = []
  if (scholarship.cuotas > 0) {
    items.push({ qty: 1, label: `Cuota: ${formatBs(scholarship.cuota)} × ${scholarship.cuotas}`, amount: formatBs(scholarship.total) })
  }
  chosen.forEach((subject, index) => {
    items.push({ qty: 1, label: `Recursado: ${subject.name}`, amount: index < charged ? formatBs(perSubject) : 'Sin cobro' })
  })

  const who = [studentName, documentNumber].filter(Boolean).join(' · ')
  return {
    title: 'UPDS COBIJA',
    subtitle: [termCode ? `Rematrícula ${termCode}` : '', who].filter(Boolean),
    items,
    total: formatBs(scholarship.total + charged * perSubject),
    notes: ['Montos informativos', 'se paga en caja'],
    limitNote: chosen.length > charged ? `Se cobran como máximo ${charged} materias.` : null,
  }
}
