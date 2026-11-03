import { teacherTypeLabel } from '@/domain/teacherTypes'
import { cn } from '@/lib/utils'
import { TONE_CHIP, type Tone } from './tones'

const TYPE_TONE: Record<string, Tone> = {
  TITULAR: 'primary',
  PERMANENTE: 'success',
  EXTERNO: 'violet',
}

function teacherTypeTone(value: string | null | undefined): Tone {
  return (value && TYPE_TONE[value.toUpperCase()]) || 'neutral'
}

export interface TeacherTypeBadgeProps {
  /** Raw teacher type (`external_permanent`). Empty renders an em dash. */
  type: string | null | undefined
  /** Display text; defaults to the domain label for the type. */
  label?: string
  className?: string
}

/** Small rounded pill per teacher type, each with its own tone. */
export function TeacherTypeBadge({ type, label, className }: TeacherTypeBadgeProps) {
  if (!type) return <span className="text-muted-foreground">—</span>
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        TONE_CHIP[teacherTypeTone(type)],
        className,
      )}
    >
      {label ?? teacherTypeLabel(type)}
    </span>
  )
}
