import { useState, useRef } from 'react'
import { useMySchedule, downloadSchedulePDF } from '@/api/hooks/useAuth'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  BookOpen,
  Users,
  Clock,
  FileDown,
  Image as ImageIcon,
  Filter,
} from 'lucide-react'
import { toPng } from 'html-to-image'
import type { PortalDesignationSchedule } from '@/api/types'

// ─── Constants ────────────────────────────────────────────────────────────────

const WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

const DAY_COLORS: Record<string, string> = {
  Lunes: '#003366',
  Martes: '#0066CC',
  Miércoles: '#4DA8DA',
  Jueves: '#16a34a',
  Viernes: '#7c3aed',
  Sábado: '#d97706',
}

const SUBJECT_PALETTE = [
  '#003366',
  '#0066CC',
  '#4DA8DA',
  '#16a34a',
  '#7c3aed',
  '#dc2626',
  '#d97706',
  '#0891b2',
  '#be185d',
  '#4338ca',
]

type ViewMode = 'dia' | 'materia' | 'grilla'
type TurnFilter = 'todos' | 'M' | 'T' | 'N'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function hashSubject(subject: string): number {
  let hash = 0
  for (let i = 0; i < subject.length; i++) {
    hash = (hash << 5) - hash + subject.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

function getSubjectColor(subject: string): string {
  return SUBJECT_PALETTE[hashSubject(subject) % SUBJECT_PALETTE.length]
}

function normDay(dia: string): string {
  return dia
    .toLowerCase()
    .replace('é', 'e')
    .replace('á', 'a')
    .replace('ó', 'o')
    .replace('ú', 'u')
    .replace('í', 'i')
}

interface FlatSlot {
  key: string
  dia: string
  hora_inicio: string
  hora_fin: string
  horas_academicas: number
  subject: string
  group_code: string
  semester: string
}

function buildFlatSlots(
  designations: PortalDesignationSchedule[],
  turnFilter: TurnFilter,
): FlatSlot[] {
  const slots: FlatSlot[] = []
  const keyOccurrences = new Map<string, number>()

  for (const d of designations) {
    if (turnFilter !== 'todos') {
      const prefix = d.group_code.charAt(0).toUpperCase()
      if (prefix !== turnFilter) continue
    }
    for (const s of d.schedule) {
      const baseKey = [
        normDay(s.dia),
        s.hora_inicio,
        s.hora_fin,
        d.subject,
        d.group_code,
        d.semester,
      ].join('|')
      const occurrence = keyOccurrences.get(baseKey) ?? 0
      keyOccurrences.set(baseKey, occurrence + 1)

      slots.push({
        key: `${baseKey}|${occurrence}`,
        dia: s.dia,
        hora_inicio: s.hora_inicio,
        hora_fin: s.hora_fin,
        horas_academicas: s.horas_academicas,
        subject: d.subject,
        group_code: d.group_code,
        semester: d.semester,
      })
    }
  }
  return slots
}

// ─── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar({ allSlots }: { allSlots: FlatSlot[] }) {
  const uniqueSubjects = new Set(allSlots.map((s) => s.subject)).size
  const uniqueGroups = new Set(allSlots.map((s) => s.group_code)).size
  const visibleHours = allSlots.reduce((sum, slot) => sum + slot.horas_academicas, 0)

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {[
        { icon: Clock, label: 'Horas visibles/semana', value: visibleHours, color: '#003366' },
        { icon: BookOpen, label: 'Materias visibles', value: uniqueSubjects, color: '#0066CC' },
        { icon: Users, label: 'Grupos visibles', value: uniqueGroups, color: '#4DA8DA' },
      ].map(({ icon: Icon, label, value, color }) => (
        <div key={label} className="card-3d-static px-4 py-3 flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: `${color}18` }}
          >
            <Icon size={16} style={{ color }} />
          </div>
          <div>
            <p className="text-lg font-bold leading-none" style={{ color }}>
              {value}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">{label}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── View: Por Día ────────────────────────────────────────────────────────────

function ViewPorDia({ allSlots }: { allSlots: FlatSlot[] }) {
  return (
    <div className="space-y-4">
      {WEEKDAYS.map((day) => {
        const dayNorm = normDay(day)
        const daySlots = allSlots
          .filter((s) => normDay(s.dia) === dayNorm)
          .sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))

        if (daySlots.length === 0) return null

        return (
          <div key={day} className="card-3d-static overflow-hidden">
            <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: DAY_COLORS[day] ?? '#003366' }}
              />
              <h4 className="text-sm font-semibold text-gray-800 capitalize">{day}</h4>
              <span className="text-xs text-gray-400 ml-auto">{daySlots.length} clase(s)</span>
            </div>
            <div className="divide-y divide-gray-100">
              {daySlots.map((slot) => (
                <div key={slot.key} className="flex flex-col items-start gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3 sm:px-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-center min-w-[72px] flex-shrink-0">
                      <p className="text-sm font-bold" style={{ color: '#003366' }}>
                        {slot.hora_inicio}
                      </p>
                      <p className="text-xs text-gray-400">{slot.hora_fin}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{slot.subject}</p>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        <Badge className="bg-blue-50 text-blue-700 border-blue-200 text-xs font-mono">
                          {slot.group_code}
                        </Badge>
                        <span className="text-xs text-gray-400">{slot.semester}</span>
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-gray-500 flex-shrink-0">{slot.horas_academicas}h</span>
                </div>
              ))}
            </div>
          </div>
        )
      })}
      {allSlots.length === 0 && (
        <div className="card-3d-static px-5 py-10 text-center">
          <p className="text-sm text-gray-400">No hay clases con los filtros seleccionados</p>
        </div>
      )}
    </div>
  )
}

// ─── View: Por Materia ────────────────────────────────────────────────────────

function ViewPorMateria({ designations, turnFilter }: { designations: PortalDesignationSchedule[]; turnFilter: TurnFilter }) {
  const filtered = designations.filter((d) => {
    if (turnFilter === 'todos') return true
    return d.group_code.charAt(0).toUpperCase() === turnFilter
  })

  if (filtered.length === 0) {
    return (
      <div className="card-3d-static px-5 py-10 text-center">
        <p className="text-sm text-gray-400">No hay materias con los filtros seleccionados</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {filtered.map((d) => {
        const color = getSubjectColor(d.subject)
        const sorted = [...d.schedule].sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio))

        return (
          <div key={`${d.subject}-${d.group_code}-${d.semester}`} className="card-3d-static overflow-hidden">
            <div
              className="px-4 py-3 flex items-center gap-3"
              style={{ background: `linear-gradient(135deg, ${color}18 0%, ${color}08 100%)` }}
            >
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: color }}
              />
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-gray-900 truncate">{d.subject}</h4>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  <Badge className="text-xs font-mono" style={{ backgroundColor: `${color}20`, color, borderColor: `${color}40` }}>
                    {d.group_code}
                  </Badge>
                  <span className="text-xs text-gray-500">{d.semester}</span>
                  {d.weekly_hours != null && (
                    <span className="text-xs text-gray-500 ml-auto">{d.weekly_hours}h/sem</span>
                  )}
                </div>
              </div>
            </div>
            {sorted.length > 0 ? (
              <div className="divide-y divide-gray-100">
                {sorted.map((slot) => (
                  <div key={`${d.subject}|${d.group_code}|${d.semester}|${normDay(slot.dia)}|${slot.hora_inicio}|${slot.hora_fin}`} className="flex flex-wrap items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-4">
                    <div
                      className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: DAY_COLORS[
                        WEEKDAYS.find((w) => normDay(w) === normDay(slot.dia)) ?? 'Lunes'
                      ] ?? color }}
                    />
                    <span className="text-xs font-medium text-gray-600 capitalize min-w-[76px]">
                      {slot.dia}
                    </span>
                    <span className="text-xs text-gray-800 font-mono">
                      {slot.hora_inicio} – {slot.hora_fin}
                    </span>
                    <span className="text-xs text-gray-400 ml-auto">{slot.horas_academicas}h</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 px-4 py-3 italic">Sin horario registrado</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── View: Grilla Semanal ─────────────────────────────────────────────────────

function ViewGrillaSemanal({ allSlots }: { allSlots: FlatSlot[] }) {
  const uniqueTimes = Array.from(new Set(allSlots.map((s) => s.hora_inicio))).sort()
  const slotsByCell = new Map<string, FlatSlot[]>()

  for (const slot of allSlots) {
    const cellKey = `${normDay(slot.dia)}|${slot.hora_inicio}`
    const cellSlots = slotsByCell.get(cellKey)
    if (cellSlots) {
      cellSlots.push(slot)
    } else {
      slotsByCell.set(cellKey, [slot])
    }
  }

  if (uniqueTimes.length === 0) {
    return (
      <div className="card-3d-static px-5 py-10 text-center">
        <p className="text-sm text-gray-400">No hay clases con los filtros seleccionados</p>
      </div>
    )
  }

  return (
    <>
      <div className="md:hidden">
        <p className="mb-3 text-xs text-gray-500">En pantallas pequeñas, la grilla se presenta como una lista por día.</p>
        <ViewPorDia allSlots={allSlots} />
      </div>
      <div className="card-3d-static hidden max-w-full overflow-hidden md:block">
        <div className="max-w-full overflow-x-auto">
          <table className="min-w-[900px] w-full text-sm">
            <caption className="sr-only">Horario semanal agrupado por día y hora de inicio</caption>
          <thead>
            <tr style={{ backgroundImage: 'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)' }}>
              <th className="px-3 py-3 text-left text-white font-semibold text-xs w-24">
                Hora
              </th>
              {WEEKDAYS.map((day) => (
                <th key={day} className="px-3 py-3 text-center text-white font-semibold text-xs capitalize">
                  {day}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {uniqueTimes.map((time, rowIdx) => {
              const bgRow = rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'

              return (
                <tr key={time} className={`border-b border-gray-100 ${bgRow}`}>
                  <td className="px-3 py-2 text-center">
                    <p className="text-xs font-mono font-bold text-gray-700">{time}</p>
                    <p className="text-[10px] text-gray-400">inicio</p>
                  </td>
                  {WEEKDAYS.map((day) => {
                    const cellSlots = slotsByCell.get(`${normDay(day)}|${time}`) ?? []

                    return (
                      <td key={day} className="align-top px-1 py-1 text-center">
                        <div className="space-y-1">
                          {cellSlots.map((slot) => {
                            const color = getSubjectColor(slot.subject)

                            return (
                              <div
                                key={slot.key}
                                className="mx-auto max-w-[140px] rounded-lg p-2 text-left"
                                style={{ backgroundColor: color, boxShadow: `0 1px 4px ${color}60` }}
                              >
                                <p className="text-xs font-semibold leading-tight text-white">{slot.subject}</p>
                                <p className="mt-1 text-[11px] text-white/90">Grupo {slot.group_code}</p>
                                <p className="text-[11px] text-white/80">{slot.semester}</p>
                                <p className="mt-1 text-[10px] font-mono text-white/75">
                                  {slot.hora_inicio}-{slot.hora_fin} · {slot.horas_academicas}h
                                </p>
                              </div>
                            )
                          })}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

// ─── Legend ───────────────────────────────────────────────────────────────────

function SubjectLegend({ designations }: { designations: PortalDesignationSchedule[] }) {
  if (designations.length === 0) return null

  return (
    <div className="card-3d-static p-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Referencias
      </p>
      <div className="flex flex-wrap gap-2">
        {designations.map((d) => {
          const color = getSubjectColor(d.subject)
          return (
            <div
              key={`${d.subject}-${d.group_code}-${d.semester}`}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{ backgroundColor: `${color}18`, color, border: `1px solid ${color}30` }}
            >
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
              {d.subject} ({d.group_code})
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function SchedulePage() {
  const { data: schedule, isLoading, error } = useMySchedule()
  const [viewMode, setViewMode] = useState<ViewMode>('dia')
  const [turnFilter, setTurnFilter] = useState<TurnFilter>('todos')
  const [isExportingPDF, setIsExportingPDF] = useState(false)
  const [isExportingImg, setIsExportingImg] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  const handleExportPDF = async () => {
    setIsExportingPDF(true)
    try {
      await downloadSchedulePDF(schedule?.teacher_name)
    } catch (e) {
      console.error('Error exporting PDF:', e)
    } finally {
      setIsExportingPDF(false)
    }
  }

  const handleExportImage = async () => {
    if (!contentRef.current) return
    setIsExportingImg(true)
    try {
      const dataUrl = await toPng(contentRef.current, {
        pixelRatio: 2,
        backgroundColor: '#ffffff',
      })
      const link = document.createElement('a')
      link.download = `horario_${schedule?.teacher_name?.replace(/\s+/g, '_') ?? 'docente'}.png`
      link.href = dataUrl
      link.click()
    } catch (e) {
      console.error('Error exporting image:', e)
    } finally {
      setIsExportingImg(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin motion-reduce:animate-none" />
      </div>
    )
  }

  if (error || !schedule) {
    return (
      <div role="alert" className="flex items-center justify-center py-24">
        <p className="text-sm text-gray-400">No se pudo cargar el horario</p>
      </div>
    )
  }

  const visibleDesignations = schedule.designations.filter((designation) => {
    if (turnFilter === 'todos') return true
    return designation.group_code.charAt(0).toUpperCase() === turnFilter
  })
  const allSlots = buildFlatSlots(visibleDesignations, 'todos')

  const viewModes: { key: ViewMode; label: string }[] = [
    { key: 'dia', label: 'Por Día' },
    { key: 'materia', label: 'Por Materia' },
    { key: 'grilla', label: 'Grilla Semanal' },
  ]

  const turnOptions: { key: TurnFilter; label: string }[] = [
    { key: 'todos', label: 'Todos los turnos' },
    { key: 'M', label: 'Mañana (M)' },
    { key: 'T', label: 'Tarde (T)' },
    { key: 'N', label: 'Noche (N)' },
  ]

  return (
    <div className="max-w-5xl space-y-4 sm:space-y-5">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold sm:text-2xl" style={{ color: '#003366' }}>
            Mi Horario Semanal
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">{schedule.teacher_name}</p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportImage}
            disabled={isExportingImg}
            className="h-9 flex-1 gap-1.5 text-xs sm:h-8 sm:flex-none"
          >
            <ImageIcon size={13} />
            {isExportingImg ? 'Exportando...' : 'Exportar Imagen'}
          </Button>
          <Button
            size="sm"
            onClick={handleExportPDF}
            disabled={isExportingPDF}
            className="h-9 flex-1 gap-1.5 text-xs text-white sm:h-8 sm:flex-none"
            style={{ backgroundColor: '#003366' }}
          >
            <FileDown size={13} />
            {isExportingPDF ? 'Generando...' : 'Exportar PDF'}
          </Button>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* View mode tabs */}
        <div className="flex max-w-full overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
          {viewModes.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setViewMode(key)}
              aria-pressed={viewMode === key}
              className={`whitespace-nowrap px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0066CC] ${
                viewMode === key
                  ? 'text-white'
                  : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
              }`}
              style={viewMode === key ? { backgroundColor: '#003366' } : undefined}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Turn filter */}
        <div className="flex items-center gap-1.5">
          <Filter size={13} className="text-gray-400" />
          <select
            aria-label="Filtrar horario por turno"
            value={turnFilter}
            onChange={(e) => setTurnFilter(e.target.value as TurnFilter)}
            className="text-xs border border-gray-200 rounded-lg px-2.5 py-2 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#003366]/30 shadow-sm"
          >
            {turnOptions.map(({ key, label }) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats */}
      <StatsBar allSlots={allSlots} />

      {/* Content (captured for image export) */}
      <div ref={contentRef} id="schedule-content" className="space-y-4">
        {/* Header for export */}
        <div className="hidden print:block">
          <p className="text-lg font-bold text-gray-900">{schedule.teacher_name} — Horario Semanal</p>
        </div>

        {viewMode === 'dia' && <ViewPorDia allSlots={allSlots} />}
        {viewMode === 'materia' && (
          <ViewPorMateria designations={visibleDesignations} turnFilter="todos" />
        )}
        {viewMode === 'grilla' && <ViewGrillaSemanal allSlots={allSlots} />}

        {/* Legend always visible */}
        <SubjectLegend designations={visibleDesignations} />
      </div>
    </div>
  )
}
