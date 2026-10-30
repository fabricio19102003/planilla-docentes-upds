import type { ContractTerms, IssueContractRequest } from '@/api/hooks/useContracts'

/** Custom contract dates as typed in the form; '' means "use the default". */
export interface ContractTermsForm {
  start: string
  end: string
  signature: string
}

const MONTHS = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

/** '2026-02-05' → '05 de febrero de 2026', as the contract writes dates. */
export function formatSpanishDate(iso: string): string {
  const [year, month, day] = iso.split('-')
  return `${day} de ${MONTHS[Number(month) - 1]} de ${year}`
}

export function toTermsForm(terms: ContractTerms): ContractTermsForm {
  return {
    start: terms.contract_start_date ?? '',
    end: terms.contract_end_date ?? '',
    signature: terms.signature_date ?? '',
  }
}

/** Same checks and messages as the server; ISO dates compare as text. */
export function validateTermsForm(form: ContractTermsForm, terms: ContractTerms): string | null {
  for (const value of [form.start, form.end]) {
    if (value && (value < terms.period_start || value > terms.period_end)) {
      return (
        `Las fechas del contrato deben estar dentro del período ${terms.academic_period} ` +
        `(${formatSpanishDate(terms.period_start)} al ${formatSpanishDate(terms.period_end)}).`
      )
    }
  }
  const start = form.start || terms.default_start
  const end = form.end || terms.default_end
  if (start && end && start > end) {
    return 'La fecha de inicio del contrato no puede ser posterior a la fecha de fin.'
  }
  return null
}

/** An empty form clears the teacher's custom dates; otherwise the filled ones replace them. */
export function buildIssuePayload(
  form: ContractTermsForm,
  department: string,
  academicPeriod: string,
): IssueContractRequest {
  const base = { department, academic_period: academicPeriod }
  if (!form.start && !form.end && !form.signature) {
    return { ...base, clear_custom_terms: true }
  }
  return {
    ...base,
    ...(form.start ? { contract_start_date: form.start } : {}),
    ...(form.end ? { contract_end_date: form.end } : {}),
    ...(form.signature ? { signature_date: form.signature } : {}),
  }
}
