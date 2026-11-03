import { Search } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control'
import type { KindFilter } from '@/lib/contractHistoryView'

const KINDS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'original', label: 'Originales' },
  { value: 'amendment', label: 'Enmiendas' },
]

interface Props {
  search: string
  onSearchChange: (value: string) => void
  period: string
  periods: string[]
  onPeriodChange: (value: string) => void
  kind: KindFilter
  counts: Record<KindFilter, number>
  onKindChange: (value: KindFilter) => void
}

/** Search, period and kind filters of the contract history. */
export function ContractHistoryToolbar({ search, onSearchChange, period, periods, onPeriodChange, kind, counts, onKindChange }: Props) {
  const periodItems = [{ value: 'all', label: 'Todos los períodos' }, ...periods.map((p) => ({ value: p, label: p }))]
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <div className="relative w-full lg:max-w-xs">
        <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          aria-label="Buscar en el historial"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Buscar por docente o CI..."
          inputClassName="pl-9"
        />
      </div>
      <Select value={period} items={periodItems} onValueChange={(value) => onPeriodChange(value ?? 'all')}>
        <SelectTrigger aria-label="Período académico" className="lg:w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectPopup>
          {periodItems.map((item) => (
            <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
          ))}
        </SelectPopup>
      </Select>
      <SegmentedControl aria-label="Tipo de documento" className="max-w-full overflow-x-auto">
        {KINDS.map((item) => (
          <SegmentedControlItem
            key={item.value}
            aria-pressed={kind === item.value}
            data-pressed={kind === item.value ? '' : undefined}
            onClick={() => onKindChange(item.value)}
          >
            {item.label}
            <span className="tabular-nums text-xs text-muted-foreground">{counts[item.value]}</span>
          </SegmentedControlItem>
        ))}
      </SegmentedControl>
    </div>
  )
}
