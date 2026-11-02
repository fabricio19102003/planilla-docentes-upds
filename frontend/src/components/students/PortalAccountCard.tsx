import { KeyRound } from 'lucide-react'
import { useState } from 'react'

import { useIssueTemporaryPassword, useSetAccountActive } from '@/api/hooks/useReenrollment'
import { ConfirmAlertDialog, type ConfirmAlertSummary } from '@/components/shared/ConfirmAlertDialog'
import { CredentialsDialog } from '@/components/students/CredentialsDialog'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { accountStatus, type PortalAccount, type TemporaryCredential } from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

function formatDateTime(value: string | null) {
  return value ? new Date(`${value}Z`).toLocaleString('es-BO', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}

export function PortalAccountCard({ studentId, account }: { studentId: number; account: PortalAccount | null }) {
  const issue = useIssueTemporaryPassword()
  const setActive = useSetAccountActive()
  const [credentials, setCredentials] = useState<TemporaryCredential[]>([])
  const [confirm, setConfirm] = useState<ConfirmAlertSummary | null>(null)
  const status = accountStatus(account)
  const error = issue.error ?? setActive.error

  const issuePassword = () => issue.mutate(studentId, {
    onSuccess: (credential) => { setConfirm(null); setCredentials([credential]) },
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          Portal del estudiante <Badge variant={status.variant}>{status.label}</Badge>
        </CardTitle>
        <CardDescription>
          {account
            ? `Último ingreso: ${formatDateTime(account.last_login)} · clave temporal generada: ${formatDateTime(account.temporary_issued_at)}`
            : 'Generá una clave temporal para que el estudiante entre con su número de documento.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        {error && <Alert variant="error" role="alert" className="w-full"><AlertTitle>{apiErrorMessage(error, 'No se pudo actualizar la cuenta.')}</AlertTitle></Alert>}
        <Button
          disabled={issue.isPending}
          onClick={() => account
            ? setConfirm({
                title: 'Generar una nueva clave temporal',
                rows: [{ label: 'Cuenta', value: status.label }],
                consequence: 'La clave actual deja de funcionar y se cierran sus sesiones abiertas.',
                confirmLabel: 'Generar clave',
              })
            : issuePassword()}
        >
          <KeyRound aria-hidden="true" />{account ? 'Generar nueva clave temporal' : 'Generar clave temporal'}
        </Button>
        {account && (
          <Button
            variant="outline"
            disabled={setActive.isPending}
            onClick={() => setActive.mutate({ studentId, active: !account.is_active })}
          >
            {account.is_active ? 'Deshabilitar cuenta' : 'Habilitar cuenta'}
          </Button>
        )}
      </CardContent>
      <ConfirmAlertDialog summary={confirm} pending={issue.isPending} onConfirm={issuePassword} onCancel={() => setConfirm(null)} />
      <CredentialsDialog credentials={credentials} onClose={() => setCredentials([])} />
    </Card>
  )
}
