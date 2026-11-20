import { Check } from 'lucide-react'

import { Meter } from '@/components/student'
import type { GroupOption } from '@/lib/reenrollmentState'
import { groupLabel } from '@/lib/studentPortalState'
import { ShiftGlyph } from './ShiftGlyph'
import { groupSeats, shiftTurnoName } from './reenrollment-view'

interface GroupCardsProps {
  groups: GroupOption[]
  mainGroup: number | null
  onChange: (id: number) => void
  disabled: boolean
}

/** Rich radio cards for the semester group: turno icon, seats meter, animated selected state. Native radios keep the keyboard semantics. */
export function GroupCards({ groups, mainGroup, onChange, disabled }: GroupCardsProps) {
  return (
    <div className="rm-groups" role="presentation">
      {groups.map((group) => {
        const selected = mainGroup === group.id
        const unavailable = group.is_full && !selected
        const seats = groupSeats(group)
        return (
          <label key={group.id} data-selected={selected ? '' : undefined} data-full={group.is_full ? '' : undefined}
            className="sp-radio-card rm-group">
            <input type="radio" name="main-group" value={group.id} checked={selected} className="rm-group-input"
              aria-label={groupLabel(group)} disabled={disabled || unavailable} onChange={() => onChange(group.id)} />
            <span className="rm-group-top">
              <span aria-hidden="true" className="sp-radio-icon rm-group-tile"><ShiftGlyph shift={group.shift} /></span>
              <span className="rm-group-code">{group.code}</span>
              <span aria-hidden="true" className="rm-group-check"><Check /></span>
            </span>
            <span className="rm-group-name">{shiftTurnoName(group.shift)}</span>
            {seats && (
              <span className="rm-group-seats" data-tone={seats.tone}>
                <span className="rm-group-seats-text">
                  <b>{seats.free}</b> de {seats.capacity} libres
                  {seats.full ? <span className="rm-group-flag">Sin cupos</span> : seats.tone === 'warn' ? <span className="rm-group-flag">Casi lleno</span> : null}
                </span>
                <Meter value={seats.occupied} max={seats.capacity} segments={seats.segments} tone={seats.tone}
                  label={`Cupos ocupados de ${group.code}`} valueText={seats.text} />
              </span>
            )}
          </label>
        )
      })}
    </div>
  )
}
