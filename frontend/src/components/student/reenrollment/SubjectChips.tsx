import { CircleCheckBig } from 'lucide-react'

import { InfoTip } from '@/components/student'
import type { CurriculumItem } from '@/lib/reenrollmentState'

function tipFor(subject: CurriculumItem): string {
  const where = `${subject.code ? `${subject.code} · ` : ''}semestre ${subject.semester}`
  return `${where}. ${subject.is_elective ? 'Materia electiva; va incluida con tu grupo.' : 'Va incluida con tu grupo del semestre.'}`
}

/** The regular subjects of the semester as chips (name + code); each one explains itself in a tip on hover, focus or tap. */
export function SubjectChips({ subjects }: { subjects: CurriculumItem[] }) {
  return (
    <ul className="rm-chips" aria-label="Materias del semestre">
      {subjects.map((subject) => (
        <li key={subject.code ?? subject.name}>
          <InfoTip content={tipFor(subject)} side="top">
            <button type="button" className="rm-chip">
              <CircleCheckBig aria-hidden="true" />
              {subject.name}
              {subject.code && <small>{subject.code}</small>}
            </button>
          </InfoTip>
        </li>
      ))}
    </ul>
  )
}
