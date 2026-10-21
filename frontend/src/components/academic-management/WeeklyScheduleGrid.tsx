import {
  activityLabel,
  GRID_DAYS,
  layoutDay,
  subjectColor,
  visibleRange,
} from '@/lib/academicScheduleGrid'
import type { ScheduleViewBlock } from '@/lib/academicScheduleGrid'

const PIXELS_PER_MINUTE = 1.3
const clock = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`

function blockTitle(block: ScheduleViewBlock) {
  return [
    block.subject_code ? `${block.subject_code} · ${block.subject_name}` : block.subject_name,
    `${activityLabel(block.activity_type)} · ${block.start_time}–${block.end_time}`,
    `Docente: ${block.teacher_name ?? (block.teacher_ci || 'Sin asignar')}`,
    `Aula: ${block.classroom_name ?? block.classroom_code ?? 'Sin aula registrada'}`,
  ].join('\n')
}

export function WeeklyScheduleGrid({ blocks, label }: { blocks: ScheduleViewBlock[]; label: string }) {
  const range = visibleRange(blocks)
  const height = (range.end - range.start) * PIXELS_PER_MINUTE
  const labels = Array.from({ length: Math.floor((range.end - range.start) / 30) + 1 }, (_, index) => range.start + index * 30)
  return (
    <div className="overflow-x-auto rounded-xl border bg-white" role="region" aria-label={label}>
      <div className="grid min-w-[900px]" style={{ gridTemplateColumns: '64px repeat(6, minmax(130px, 1fr))' }}>
        <div className="sticky top-0 border-b bg-slate-50" />
        {GRID_DAYS.map(([, name]) => (
          <div key={name} className="border-b border-l bg-slate-50 px-2 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-600">{name}</div>
        ))}
        <div className="relative border-r" style={{ height }} aria-hidden="true">
          {labels.map((minutes) => (
            <span key={minutes} className="absolute right-2 -translate-y-1/2 text-[11px] tabular-nums text-slate-400" style={{ top: (minutes - range.start) * PIXELS_PER_MINUTE }}>{clock(minutes)}</span>
          ))}
        </div>
        {GRID_DAYS.map(([weekday, name]) => (
          <div key={weekday} className="relative border-l" style={{ height }}>
            {labels.map((minutes) => (
              <div key={minutes} aria-hidden="true" className="absolute inset-x-0 border-t border-slate-100" style={{ top: (minutes - range.start) * PIXELS_PER_MINUTE }} />
            ))}
            <ul aria-label={`Clases del ${name.toLowerCase()}`}>
              {layoutDay(blocks.filter((block) => block.weekday === weekday), range).map((item) => {
                const color = subjectColor(item.block.subject_name)
                const practice = item.block.activity_type === 'practice'
                const width = 100 / item.columns
                return (
                  <li
                    key={item.block.key}
                    title={blockTitle(item.block)}
                    className={`absolute overflow-hidden rounded-md border-l-4 px-1.5 py-1 text-[11px] leading-tight shadow-sm ${practice ? 'border-dashed' : ''}`}
                    style={{
                      top: `${item.top}%`, height: `calc(${item.height}% - 2px)`,
                      left: `calc(${item.column * width}% + 2px)`, width: `calc(${width}% - 4px)`,
                      background: color.background, borderColor: color.border, color: color.text,
                      borderStyle: practice ? 'dashed' : 'solid', borderWidth: practice ? '1px 1px 1px 4px' : undefined,
                    }}
                  >
                    <p className="font-semibold">{item.block.subject_name}</p>
                    <p className="tabular-nums opacity-80">{item.block.start_time}–{item.block.end_time} · {practice ? <em>Práctica</em> : 'Teoría'}</p>
                    <p className="truncate">{item.block.teacher_name ?? (item.block.teacher_ci || 'Sin docente')}</p>
                    {(item.block.classroom_name || item.block.classroom_code) && <p className="truncate opacity-80">{item.block.classroom_name ?? item.block.classroom_code}</p>}
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
