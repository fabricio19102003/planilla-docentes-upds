import { CircleAlert, ClipboardCheck, Flag, IdCard, Mail, Phone, type LucideIcon } from 'lucide-react'

import { Eyebrow, InfoTip, Sheet } from '@/components/student'
import { dataValue } from './home-state'

export interface StudentData {
  document_number: string | null
  curriculum_plan: string | null
  phone: string | null
  academic_email: string | null
  personal_email: string | null
  nationality: string | null
}

const FIELDS: { label: string; key: keyof StudentData; icon: LucideIcon }[] = [
  { label: 'Documento', key: 'document_number', icon: IdCard },
  { label: 'Plan de estudio', key: 'curriculum_plan', icon: ClipboardCheck },
  { label: 'Celular', key: 'phone', icon: Phone },
  { label: 'Correo académico', key: 'academic_email', icon: Mail },
  { label: 'Correo personal', key: 'personal_email', icon: Mail },
  { label: 'Nacionalidad', key: 'nationality', icon: Flag },
]

/** Mis datos as an icon grid; a missing value is a styled "Sin dato" with a tip, not a bare dash. */
export function DataGrid({ data }: { data: StudentData }) {
  return (
    <section aria-labelledby="sph-datos">
    <Sheet depth={2} padding="md" lift className="sph-data-sheet">
      <header className="sph-sheet-head">
        <div className="grid gap-3">
          <Eyebrow>Mis datos</Eyebrow>
          <h2 id="sph-datos" className="sp-title">Lo que Registro tiene de vos</h2>
        </div>
        <p className="sph-sub">Si algo está mal, avisá en Registro.</p>
      </header>
      <ul className="sph-data">
        {FIELDS.map(({ label, key, icon: Icon }) => {
          const value = dataValue(data[key])
          return (
            <li key={key + label} className="sph-data-item">
              <span aria-hidden="true" className="sph-tile"><Icon /></span>
              <span className="sph-data-body">
                <span className="sph-data-label">{label}</span>
                {value ? (
                  <span className="sph-data-value">{value}</span>
                ) : (
                  <InfoTip content={`Registro todavía no tiene tu ${label.toLowerCase()}. Avisá en Registro para completarlo.`}>
                    <span className="sph-missing" tabIndex={0}>
                      <CircleAlert aria-hidden="true" />Sin dato
                    </span>
                  </InfoTip>
                )}
              </span>
            </li>
          )
        })}
      </ul>
    </Sheet>
    </section>
  )
}
