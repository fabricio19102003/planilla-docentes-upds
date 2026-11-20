import { AlertCircle, GraduationCap, IdCard, KeyRound, LogIn } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useStudentLogin } from '@/api/hooks/useStudentPortal'
import { AccessCard } from '@/components/student/access/AccessCard'
import { AccessInput } from '@/components/student/access/AccessInput'
import { StudentPasswordField } from '@/components/student/access/StudentPasswordField'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Field, FieldLabel } from '@/components/ui/field'
import { apiErrorMessage } from '@/lib/userCredentials'
import '@/styles/student/access.css'

export function StudentLoginPage() {
  const navigate = useNavigate()
  const login = useStudentLogin()
  const [documentNumber, setDocumentNumber] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    login.mutate({ document_number: documentNumber.trim(), password }, {
      onSuccess: (session) => navigate(session.must_change_password ? '/estudiante/cambiar-clave' : '/estudiante', { replace: true }),
    })
  }

  return (
    <main className="student-scope font-student bg-brand sa-root">
      <AccessCard
        icon={<GraduationCap />} eyebrow="Estudiantes" shake={login.isError}
        title="Portal del estudiante"
        lead="Entrá con tu número de documento. La primera vez usá la clave temporal que te dio Registro."
      >
        <form onSubmit={submit} className="sa-form">
          <Field>
            <FieldLabel htmlFor="student-document" className="sa-label">Número de documento</FieldLabel>
            <AccessInput id="student-document" value={documentNumber} onChange={setDocumentNumber} icon={<IdCard />}
              autoComplete="username" placeholder="Ej: 7485000 o I-11626046" />
          </Field>
          <Field>
            <FieldLabel htmlFor="student-password" className="sa-label">Contraseña</FieldLabel>
            <StudentPasswordField id="student-password" value={password} onChange={setPassword} placeholder="Tu contraseña"
              disabled={login.isPending} invalid={login.isError} visible={visible} onToggle={() => setVisible((v) => !v)}
              autoComplete="current-password" />
          </Field>
          {login.isError && (
            <Alert variant="error" role="alert">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>{apiErrorMessage(login.error, 'No se pudo iniciar sesión. Intentá de nuevo.')}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" size="lg" loading={login.isPending} disabled={!documentNumber.trim() || !password}
            className="sa-submit w-full active:scale-95 motion-reduce:active:scale-100">
            <LogIn aria-hidden="true" />Ingresar
          </Button>
          <p className="sa-hint"><KeyRound aria-hidden="true" />¿Olvidaste tu contraseña? Pedí una clave temporal nueva en Registro.</p>
        </form>
      </AccessCard>
    </main>
  )
}
