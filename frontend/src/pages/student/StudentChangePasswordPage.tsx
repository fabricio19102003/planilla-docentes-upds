import { AlertCircle, Lock } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useStudentChangePassword, useStudentMe } from '@/api/hooks/useStudentPortal'
import { STUDENT_TOKEN_KEY } from '@/api/studentClient'
import { Logo } from '@/components/layout/Logo'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { PasswordInput, PasswordStrengthBar, ValidationItem } from '@/pages/ForceChangePasswordPage'
import { apiErrorMessage } from '@/lib/userCredentials'

export function StudentChangePasswordPage() {
  const navigate = useNavigate()
  const me = useStudentMe()
  const change = useStudentChangePassword()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [visible, setVisible] = useState(false)

  if (!localStorage.getItem(STUDENT_TOKEN_KEY)) return <Navigate to="/estudiante/login" replace />

  const rules = [
    [next.length >= 8, 'Al menos 8 caracteres'],
    [/[A-Z]/.test(next), 'Una mayúscula'],
    [/[a-z]/.test(next), 'Una minúscula'],
    [/\d/.test(next), 'Un número'],
    [next !== '' && next === confirm, 'Las dos contraseñas coinciden'],
  ] as const
  const valid = rules.every(([passes]) => passes) && current !== ''
  const toggle = { visible, onToggle: () => setVisible((v) => !v), toggleLabel: visible ? 'Ocultar contraseñas' : 'Mostrar contraseñas' }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-md p-6 sm:p-8">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Logo />
          <h1 className="flex items-center gap-2 text-xl font-semibold"><Lock aria-hidden="true" />Creá tu contraseña</h1>
          <p className="text-sm text-muted-foreground">
            {me.data?.must_change_password === false ? 'Cambiá tu contraseña del portal.' : 'Antes de seguir, reemplazá la clave temporal por una contraseña tuya.'}
          </p>
        </div>
        <form className="space-y-5" onSubmit={(event) => {
          event.preventDefault()
          change.mutate({ current_password: current, new_password: next }, { onSuccess: () => navigate('/estudiante', { replace: true }) })
        }}>
          <Field>
            <FieldLabel htmlFor="student-current">Clave actual (la temporal si es tu primer ingreso)</FieldLabel>
            <PasswordInput id="student-current" value={current} onChange={setCurrent} placeholder="Clave actual" disabled={change.isPending} invalid={false} {...toggle} />
          </Field>
          <Field>
            <FieldLabel htmlFor="student-new">Nueva contraseña</FieldLabel>
            <PasswordInput id="student-new" value={next} onChange={setNext} placeholder="Nueva contraseña" disabled={change.isPending} invalid={false} {...toggle} />
            <PasswordStrengthBar password={next} />
          </Field>
          <Field>
            <FieldLabel htmlFor="student-confirm">Repetí la nueva contraseña</FieldLabel>
            <PasswordInput id="student-confirm" value={confirm} onChange={setConfirm} placeholder="Repetila" disabled={change.isPending} invalid={false} {...toggle} />
          </Field>
          <div className="space-y-1">{rules.map(([passes, label]) => <ValidationItem key={label} passes={passes} label={label} />)}</div>
          {change.isError && (
            <Alert variant="error" role="alert">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>{apiErrorMessage(change.error, 'No se pudo cambiar la contraseña.')}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" size="lg" loading={change.isPending} disabled={!valid} className="w-full">Guardar contraseña</Button>
        </form>
      </Card>
    </main>
  )
}
