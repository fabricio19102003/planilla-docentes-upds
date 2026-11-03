import { AlertCircle, GraduationCap, LogIn } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useStudentLogin } from '@/api/hooks/useStudentPortal'
import { Logo } from '@/components/layout/Logo'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/pages/ForceChangePasswordPage'
import { apiErrorMessage } from '@/lib/userCredentials'

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
    <main className="bg-brand flex min-h-screen flex-col items-center justify-center p-4">
      <div className="mb-6 rounded-2xl border border-brand-foreground/15 bg-brand-foreground/10 px-8 py-5 shadow-lg shadow-brand/30 backdrop-blur">
        <Logo />
      </div>
      <Card className="w-full max-w-md overflow-hidden p-6 shadow-2xl shadow-brand/40 sm:p-8">
        <span aria-hidden="true" className="bg-brand-line absolute inset-x-0 top-0 h-1" />
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-brand"><GraduationCap aria-hidden="true" />Portal del estudiante</h1>
          <p className="text-sm text-muted-foreground">Entrá con tu número de documento. La primera vez usá la clave temporal que te dio Registro.</p>
        </div>
        <form onSubmit={submit} className="space-y-5">
          <Field>
            <FieldLabel htmlFor="student-document">Número de documento</FieldLabel>
            <Input id="student-document" value={documentNumber} autoComplete="username" placeholder="Ej: 7485000 o I-11626046"
              onChange={(event) => setDocumentNumber(event.target.value)} />
          </Field>
          <Field>
            <FieldLabel htmlFor="student-password">Contraseña</FieldLabel>
            <PasswordInput id="student-password" value={password} onChange={setPassword} placeholder="Tu contraseña"
              disabled={login.isPending} invalid={login.isError} visible={visible} onToggle={() => setVisible((v) => !v)}
              toggleLabel={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'} />
          </Field>
          {login.isError && (
            <Alert variant="error" role="alert">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>{apiErrorMessage(login.error, 'No se pudo iniciar sesión. Intentá de nuevo.')}</AlertDescription>
            </Alert>
          )}
          <Button type="submit" size="lg" loading={login.isPending} disabled={!documentNumber.trim() || !password} className="w-full">
            <LogIn aria-hidden="true" />Ingresar
          </Button>
          <p className="text-center text-xs text-muted-foreground">¿Olvidaste tu contraseña? Pedí una clave temporal nueva en Registro.</p>
        </form>
      </Card>
    </main>
  )
}
