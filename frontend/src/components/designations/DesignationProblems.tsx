import { TriangleAlert } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { ProblemDetails } from '@/lib/designationAdminState'

/** One error box for the form checks and for server refusals (validation, paid months, contracts). */
export function DesignationProblems({ problems }: { problems: ProblemDetails | null }) {
  if (!problems) return null
  return (
    <Alert variant="error" role="alert">
      <TriangleAlert aria-hidden="true" />
      <AlertTitle>{problems.title}</AlertTitle>
      {problems.items.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-4">
            {problems.items.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </AlertDescription>
      )}
    </Alert>
  )
}
