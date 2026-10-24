import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import { resolveTone, TONE_CHIP, TONE_TEXT, type Tone } from './tones'

export interface StatCardTrend {
  /** Short text such as "+12% vs. mes anterior". */
  label: string
  /** `up` renders in the success tone, `down` in the destructive tone. Defaults to `flat`. */
  direction?: 'up' | 'down' | 'flat'
}

export interface StatCardProps {
  icon: LucideIcon
  title: string
  value: string | number
  /** Muted line under the value. */
  subtitle?: string
  /** Same slot as `subtitle` but accepts nodes; wins over `subtitle` when both are given. */
  hint?: ReactNode
  /** Optional trend line shown under the hint. */
  trend?: StatCardTrend
  /** Semantic tone of the icon chip. Defaults to `primary`. */
  tone?: Tone
  /** @deprecated Use `tone`. Legacy CSS color, mapped onto the closest tone by hue. */
  color?: string
  /** @deprecated Use `tone`. Legacy gradient class name, mapped onto a tone. */
  gradient?: string
  className?: string
}

const TREND_ICON = { up: ArrowUpRight, down: ArrowDownRight, flat: ArrowRight } as const
const TREND_TONE: Record<NonNullable<StatCardTrend['direction']>, Tone> = {
  up: 'success',
  down: 'destructive',
  flat: 'neutral',
}

/**
 * Summary metric: a soft tinted icon chip, a tabular-nums value and an optional hint or trend line.
 *
 * @example
 * <StatCard icon={Users} title="Docentes" value={42} tone="primary" hint="Activos este mes" />
 */
export function StatCard({ icon: Icon, title, value, subtitle, hint, trend, tone, color, gradient, className }: StatCardProps) {
  const resolved = resolveTone({ tone, color, gradient })
  const hintContent = hint ?? subtitle
  const TrendIcon = trend ? TREND_ICON[trend.direction ?? 'flat'] : null

  return (
    <Card className={cn('flex-row items-center gap-3 p-4 sm:gap-4 sm:p-5', className)}>
      <div className={cn('flex size-9 shrink-0 sm:size-11 items-center justify-center rounded-xl', TONE_CHIP[resolved])}>
        <Icon className="size-4 sm:size-5" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-muted-foreground">{title}</p>
        <p className="truncate text-2xl font-semibold leading-tight tracking-tight tabular-nums text-foreground">{value}</p>
        {hintContent != null && hintContent !== '' && (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{hintContent}</p>
        )}
        {trend && TrendIcon && (
          <p className={cn('mt-0.5 flex items-center gap-1 text-xs font-medium', TONE_TEXT[TREND_TONE[trend.direction ?? 'flat']])}>
            <TrendIcon className="size-3.5" aria-hidden="true" />
            <span className="truncate">{trend.label}</span>
          </p>
        )}
      </div>
    </Card>
  )
}
