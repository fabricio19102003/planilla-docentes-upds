import { AlertCircle, Lock, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useStudentChangePassword, useStudentMe } from '@/api/hooks/useStudentPortal'
import { STUDENT_TOKEN_KEY } from '@/api/studentClient'
import { AccessCard } from '@/components/student/access/AccessCard'
import { PasswordChecklist } from '@/components/student/access/PasswordChecklist'
import { PasswordStrength } from '@/components/student/access/PasswordStrength'
import { StudentPasswordField } from '@/components/student/access/StudentPasswordField'
import { passwordRules } from '@/components/student/access/student-access'
import { InfoTip } from '@/components/student/InfoTip'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { apiErrorMessage } from '@/lib/userCredentials'
import '@/styles/student/access.css'

export function StudentChangePasswordPage() {
  const navigate = useNavigate()
  const me = useStudentMe()
  const change = useStudentChangePassword()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [visible, setVisible] = useState(false)

  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) return <Navigate to="/estudiante/login" replace />

  const rules = passwordRules(next, confirm)
  const valid = rules.every((rule) => rule.passes) && current !== ''
  const toggle = { visible, onToggle: () => setVisible((v) => !v), plural: true, disabled: change.isPending, invalid: false }

  return (
    <main className="student-scope font-student bg-brand sa-root">
      <AccessCard
        icon={<Lock />} eyebrow="Tu cuenta" shake={change.isError}
        title="Creá tu contraseña"
        lead={me.data?.must_change_password === false ? 'Cambiá tu contraseña del portal.' : 'Antes de seguir, reemplazá la clave temporal por una contraseña tuya.'}
      >
        <form className="sa-form" onSubmit={(event) => {
          event.preventDefault()
          change.mutate({ current_password: current, new_password: next }, { onSuccess: () => navigate('/estudiante', { replace: true }) })
        }}>
          <Field>
            <div className="sa-label-row">
              <FieldLabel htmlFor="student-current" className="sa-label">Clave actual</FieldLabel>
              <InfoTip label="Qué clave usar" content="Clave actual (la temporal si es tu primer ingreso): es la que te dio Registro." />
            </div>
            <StudentPasswordField id="student-current" value={current} onChange={setCurrent} placeholder="Clave actual" autoComplete="current-password" {...toggle} />
          </Field>
          <Field>
            <FieldLabel htmlFor="student-new" className="sa-label">Nueva contraseña</FieldLabel>
            <StudentPasswordField id="student-new" value={next} onChange={setNext} placeholder="Nueva contraseña" autoComplete="new-password" {...toggle} />
            <PasswordStrength password={next} />
          </Field>
          <Field>
            <FieldLabel htmlFor="student-confirm" className="sa-label">Repetí la nueva contraseña</FieldLabel>
            <StudentPasswordField id="student-confirm" value={confirm} onChange={setConfirm} placeholder="Repetila" autoComplete="new-password" {...toggle} />
          </Field>
          <PasswordChecklist rules={rules} />
          {change.isError && (
            <Alert variant="error" role="alert">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>{apiErrorMessage(change.error, 'No se pudo cambiar la contraseña.')}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" size="lg" loading={change.isPending} disabled={!valid}
            className="sa-submit w-full active:scale-95 motion-reduce:active:scale-100">
            <ShieldCheck aria-hidden="true" />Guardar contraseña
          </Button>
        </form>
      </AccessCard>
    </main>
  )
}
