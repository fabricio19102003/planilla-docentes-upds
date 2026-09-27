import { api } from '@/api/client'
import type {
  DesignationBootstrapAliasSelections,
  DesignationBootstrapApplyResult,
  DesignationBootstrapPreview,
  DesignationBootstrapResolutionContext,
} from '@/api/types'

export const DESIGNATION_BOOTSTRAP_PERIOD = 'II/2026'
export const DESIGNATION_BOOTSTRAP_EFFECTIVE_DATE = '2026-08-21'

export interface DesignationBootstrapFiles {
  officialWorkbook: File
  salaryWorkbook: File
  aliasResolution?: File
  programIdentity: string
}

export type DesignationBootstrapSources = Pick<
  DesignationBootstrapFiles,
  'officialWorkbook' | 'salaryWorkbook'
>

function designationBootstrapSourceForm(payload: DesignationBootstrapSources) {
  const formData = new FormData()
  formData.append('official_workbook', payload.officialWorkbook)
  formData.append('salary_workbook', payload.salaryWorkbook)
  formData.append('academic_period', DESIGNATION_BOOTSTRAP_PERIOD)
  formData.append('effective_date', DESIGNATION_BOOTSTRAP_EFFECTIVE_DATE)
  return formData
}

function designationBootstrapForm(payload: DesignationBootstrapFiles) {
  const formData = designationBootstrapSourceForm(payload)
  if (payload.aliasResolution) formData.append('alias_resolution', payload.aliasResolution)
  formData.append('academic_period', DESIGNATION_BOOTSTRAP_PERIOD)
  formData.append('effective_date', DESIGNATION_BOOTSTRAP_EFFECTIVE_DATE)
  formData.append('program_identity', payload.programIdentity)
  return formData
}

export async function getDesignationBootstrapResolutionContext(payload: DesignationBootstrapSources) {
  const response = await api.post<DesignationBootstrapResolutionContext>(
    '/admin/academic-management/designation-bootstrap/resolution-context',
    designationBootstrapSourceForm(payload),
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return response.data
}

export async function createDesignationBootstrapAliasArtifact(
  payload: DesignationBootstrapSources,
  resolutionToken: string,
  selections: DesignationBootstrapAliasSelections,
) {
  const formData = designationBootstrapSourceForm(payload)
  formData.append('resolution_token', resolutionToken)
  formData.append('selections', JSON.stringify(selections))
  const response = await api.post<Blob>(
    '/admin/academic-management/designation-bootstrap/alias-artifact',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob',
    },
  )
  return response.data
}

export async function previewDesignationBootstrap(payload: DesignationBootstrapFiles) {
  const response = await api.post<DesignationBootstrapPreview>(
    '/admin/academic-management/designation-bootstrap/preview',
    designationBootstrapForm(payload),
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return response.data
}

export async function applyDesignationBootstrap(
  payload: DesignationBootstrapFiles,
  confirmationDigest: string,
) {
  const formData = designationBootstrapForm(payload)
  formData.append('confirmation_digest', confirmationDigest)
  const response = await api.post<DesignationBootstrapApplyResult>(
    '/admin/academic-management/designation-bootstrap/apply',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return response.data
}
