// Pure helpers for editing the curriculum and generating a period's offerings from it.

export interface SlotForm {
  semester: string
  name: string
  code: string
  theory_hours: string
  practice_hours: string
  credits: string
  is_elective: boolean
}

export interface SlotPayload {
  semester: number
  name: string
  code: string | null
  theory_hours: number
  practice_hours: number
  credits: number
  is_elective: boolean
}

export interface OfferingGeneration {
  academic_period: string
  created: string[]
  existing: string[]
  skipped: { name: string; semester: number; reason: string }[]
}

const CODE = /^[A-Z]{3} [0-9]{4}$/
const WHOLE = /^[0-9]+$/

export function emptySlotForm(semester: number): SlotForm {
  return { semester: String(semester), name: '', code: '', theory_hours: '0', practice_hours: '0', credits: '0', is_elective: false }
}

export function slotFormProblem(form: SlotForm): string | null {
  if (!form.name.trim()) return 'Escribí el nombre de la materia.'
  const code = form.code.trim().toUpperCase()
  if (code && !CODE.test(code)) return 'La sigla va con 3 letras, un espacio y 4 números (ej: BIO 0300).'
  if (!code && !form.is_elective) return 'Una materia que no es electiva necesita sigla.'
  if (![form.theory_hours, form.practice_hours, form.credits].every((v) => WHOLE.test(v.trim()))) {
    return 'Las horas y los créditos son números enteros desde 0.'
  }
  if (Number(form.theory_hours) === 0 && Number(form.practice_hours) === 0) {
    return 'La materia necesita al menos una hora teórica o práctica.'
  }
  return null
}

export function slotPayload(form: SlotForm): SlotPayload {
  const code = form.code.trim().toUpperCase()
  return {
    semester: Number(form.semester), name: form.name.trim(), code: code || null,
    theory_hours: Number(form.theory_hours), practice_hours: Number(form.practice_hours), credits: Number(form.credits),
    is_elective: form.is_elective,
  }
}

export function moveSlot(ids: number[], id: number, direction: 'up' | 'down'): number[] {
  const index = ids.indexOf(id)
  const target = direction === 'up' ? index - 1 : index + 1
  if (index < 0 || target < 0 || target >= ids.length) return ids
  const next = [...ids]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

function count(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`
}

export function offeringSummary(result: OfferingGeneration): string {
  return `${result.academic_period}: ${count(result.created.length, 'oferta creada', 'ofertas creadas')}, `
    + `${count(result.existing.length, 'ya existía', 'ya existían')}, ${count(result.skipped.length, 'no generada', 'no generadas')}.`
}
