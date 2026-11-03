import { StatusBadge } from '@/components/shared/StatusBadge'
import { TONE_CHIP } from '@/components/shared/tones'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { ContractLine } from '@/api/hooks/useContracts'
import { changeKindLabel, changeKindTone } from '@/lib/contractHistoryView'
import { cn } from '@/lib/utils'

const ACTIVITY = {
  theory: { label: 'Teoría', chip: TONE_CHIP.violet },
  practice: { label: 'Práctica', chip: TONE_CHIP.cyan },
} as const

/** Lines of one contract document: activity chip, subject, hours, rate and the kind of change. */
export function ContractLinesTable({ lines, documentLabel }: { lines: ContractLine[]; documentLabel: string }) {
  return (
    <div className="rounded-lg border">
      <Table aria-label={`Líneas de ${documentLabel}`}>
        <TableHeader>
          <TableRow>
            <TableHead>Actividad</TableHead>
            <TableHead>Materia</TableHead>
            <TableHead className="text-right">Horas</TableHead>
            <TableHead className="text-right">Tarifa</TableHead>
            <TableHead>Cambio</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => {
            const activity = ACTIVITY[line.activity_kind]
            return (
              <TableRow key={line.line_number}>
                <TableCell>
                  <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap', activity.chip)}>
                    {activity.label}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="font-medium text-foreground">{line.subject_label}</span>
                  <span className="text-muted-foreground"> ({line.group_label})</span>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {line.hours} h
                  {line.previous_hours != null && line.previous_hours !== line.hours && (
                    <span className="block text-xs text-muted-foreground">antes {line.previous_hours} h</span>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  Bs {line.hourly_rate}
                  {line.previous_hourly_rate != null && line.previous_hourly_rate !== line.hourly_rate && (
                    <span className="block text-xs text-muted-foreground">antes Bs {line.previous_hourly_rate}</span>
                  )}
                </TableCell>
                <TableCell>
                  {line.change_kind !== 'full' && (
                    <StatusBadge tone={changeKindTone(line.change_kind)}>{changeKindLabel(line.change_kind)}</StatusBadge>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
