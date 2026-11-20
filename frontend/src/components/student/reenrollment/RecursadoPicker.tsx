import { History, Repeat } from 'lucide-react'
import { useState } from 'react'

import { Select, SelectItem, SelectPopup, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { CurriculumItem, GroupOption } from '@/lib/reenrollmentState'
import { shiftLabel, type GroupChoices } from '@/lib/studentPortalState'
import { ShiftGlyph } from './ShiftGlyph'
import { groupSeats } from './reenrollment-view'

const NONE = 'none'

function GroupRow({ group }: { group: GroupOption }) {
  const seats = groupSeats(group)
  return (
    <span className="rm-opt">
      <ShiftGlyph shift={group.shift} />
      <span className="rm-opt-name">{group.code} · {shiftLabel(group.shift)}</span>
      {seats && <small>{group.is_full ? 'Sin cupos' : seats.text}</small>}
    </span>
  )
}

interface SubjectPickerProps {
  subject: CurriculumItem
  kind: 'recursado' | 'pendiente'
  groups: GroupOption[]
  choice: number | ''
  setChoice: (code: string, group: number | '') => void
  disabled: boolean
}

/** One subject: a switch to take it this term and an accessible listbox (base-ui Select) of groups; "No la curso este período" is still an option. */
function SubjectPicker({ subject, kind, groups, choice, setChoice, disabled }: SubjectPickerProps) {
  const code = subject.code ?? subject.name
  const [wants, setWants] = useState(choice !== '')
  const on = wants || choice !== ''
  const Icon = kind === 'recursado' ? Repeat : History
  const items = [
    { value: NONE, label: 'No la curso este período' },
    ...groups.map((group) => ({ value: String(group.id), label: <GroupRow group={group} /> })),
  ]

  const toggle = () => {
    if (on) {
      setWants(false)
      setChoice(code, '')
      return
    }
    setWants(true)
    // Turning it on picks the first group with seats, so the receipt reflects it right away.
    const first = groups.find((group) => !group.is_full)
    if (first) setChoice(code, first.id)
  }

  return (
    <li className="rm-rec" data-on={on ? '' : undefined}>
      <div className="rm-rec-top">
        <span aria-hidden="true" className="rm-rec-tile"><Icon /></span>
        <div className="rm-rec-id">
          <h3>{subject.name}</h3>
          <p>{subject.code && <code>{subject.code}</code>}{subject.code && ' · '}semestre {subject.semester}</p>
        </div>
        <button type="button" role="switch" aria-checked={on} className="rm-switch" disabled={disabled}
          aria-label={`${kind === 'recursado' ? 'Recursar' : 'Cursar'} ${subject.name}`} onClick={toggle}>
          {kind === 'recursado' ? 'Recursar' : 'Cursar'}
          <span aria-hidden="true" className="rm-switch-track" />
        </button>
      </div>
      {on && (
        <div className="rm-rec-pick">
          <span aria-hidden="true" className="rm-label">Grupo y turno</span>
          <Select<string> items={items} value={choice === '' ? null : String(choice)} disabled={disabled}
            onValueChange={(value) => {
              if (value === null || value === NONE) {
                setWants(false)
                setChoice(code, '')
              } else setChoice(code, Number(value))
            }}>
            <SelectTrigger className="rm-select" aria-label={`Grupo y turno de ${subject.name}`}>
              <SelectValue>
                {(value: string | null) => {
                  const group = groups.find((item) => String(item.id) === value)
                  return group ? <GroupRow group={group} /> : <span className="rm-placeholder">Elegí grupo y turno</span>
                }}
              </SelectValue>
            </SelectTrigger>
            <SelectPopup className="rm-list" alignItemWithTrigger={false} sideOffset={8}>
              {items.map((item) => {
                const group = groups.find((entry) => String(entry.id) === item.value)
                return (
                  <SelectItem key={item.value} value={item.value} className="rm-item"
                    disabled={group ? group.is_full && choice !== group.id : false}>
                    {item.label}
                  </SelectItem>
                )
              })}
            </SelectPopup>
          </Select>
        </div>
      )}
    </li>
  )
}

interface RecursadoPickerProps {
  kind: 'recursado' | 'pendiente'
  subjects: CurriculumItem[]
  groupsBySemester: Record<string, GroupOption[]>
  choices: GroupChoices
  setChoice: (code: string, group: number | '') => void
  disabled: boolean
}

export function RecursadoPicker({ kind, subjects, groupsBySemester, choices, setChoice, disabled }: RecursadoPickerProps) {
  return (
    <ul className="rm-recs">
      {subjects.map((subject) => (
        <SubjectPicker key={subject.code ?? subject.name} subject={subject} kind={kind} disabled={disabled}
          groups={groupsBySemester[String(subject.semester)] ?? []} choice={choices[subject.code ?? subject.name] ?? ''} setChoice={setChoice} />
      ))}
    </ul>
  )
}
