const dateFormatter = new Intl.DateTimeFormat('es-BO', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

const dateTimeFormatter = new Intl.DateTimeFormat('es-BO', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

const currencyFormatter = new Intl.NumberFormat('es-BO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export const monthOptions = [
  { value: '1', label: 'Enero' },
  { value: '2', label: 'Febrero' },
  { value: '3', label: 'Marzo' },
  { value: '4', label: 'Abril' },
  { value: '5', label: 'Mayo' },
  { value: '6', label: 'Junio' },
  { value: '7', label: 'Julio' },
  { value: '8', label: 'Agosto' },
  { value: '9', label: 'Septiembre' },
  { value: '10', label: 'Octubre' },
  { value: '11', label: 'Noviembre' },
  { value: '12', label: 'Diciembre' },
] as const

export const yearOptions = Array.from({ length: 5 }, (_, index) => {
  const year = new Date().getFullYear() - 1 + index

  return {
    value: String(year),
    label: String(year),
  }
})

export function getCurrentPeriod() {
  const now = new Date()

  return {
    month: now.getMonth() + 1,
    year: now.getFullYear(),
  }
}

export function formatDate(value?: string | null) {
  if (!value) {
    return '--'
  }

  return dateFormatter.format(new Date(value))
}

export function formatDateTime(value?: string | null) {
  if (!value) {
    return '--'
  }

  return dateTimeFormatter.format(new Date(value))
}

export function formatCurrency(value?: number | string | null) {
  const amount = Number(value ?? 0)

  return `Bs ${currencyFormatter.format(Number.isNaN(amount) ? 0 : amount)}`
}

export function formatTime(value?: string | null) {
  return value?.slice(0, 5) ?? '--'
}

export function formatPercentage(value?: number | null) {
  return `${Number(value ?? 0).toFixed(1)}%`
}

export function getPageCount(total: number, perPage: number) {
  return Math.max(1, Math.ceil(total / perPage))
}
