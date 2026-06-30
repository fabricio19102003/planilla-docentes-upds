const BOLIVIA_TIME_ZONE = 'America/La_Paz'
const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/

const boliviaDateFormatter = new Intl.DateTimeFormat('es-BO', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: BOLIVIA_TIME_ZONE,
})

const boliviaShortDateFormatter = new Intl.DateTimeFormat('es-BO', {
  day: '2-digit',
  month: '2-digit',
  timeZone: BOLIVIA_TIME_ZONE,
})

const boliviaDatePartsFormatter = new Intl.DateTimeFormat('en-CA', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: BOLIVIA_TIME_ZONE,
})

export function formatDateInBolivia(dateStr: string): string {
  const dateOnly = DATE_ONLY_PATTERN.exec(dateStr)
  if (dateOnly) {
    const [, year, month, day] = dateOnly
    return `${day}/${month}/${year}`
  }

  return boliviaDateFormatter.format(new Date(dateStr))
}

export function formatShortDateInBolivia(dateStr: string | null): string {
  if (!dateStr) return '—'

  const dateOnly = DATE_ONLY_PATTERN.exec(dateStr)
  if (dateOnly) {
    const [, , month, day] = dateOnly
    return `${day}/${month}`
  }

  return boliviaShortDateFormatter.format(new Date(dateStr))
}

export function getTodayInBolivia(now = new Date()): string {
  const parts = boliviaDatePartsFormatter.formatToParts(now)
  const getPart = (type: string) => parts.find(part => part.type === type)?.value ?? ''

  return `${getPart('year')}-${getPart('month')}-${getPart('day')}`
}
