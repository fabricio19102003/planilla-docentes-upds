import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ContractRequest {
  department: string
  academic_period?: string
}

/** Single-teacher issue: any date sent replaces the teacher's custom dates. */
export interface IssueContractRequest extends ContractRequest {
  contract_start_date?: string
  contract_end_date?: string
  signature_date?: string
  clear_custom_terms?: boolean
}

/** Default dates from the teacher's load and the custom dates in effect (ISO dates). */
export interface ContractTerms {
  academic_period: string
  period_start: string
  period_end: string
  default_start: string | null
  default_end: string | null
  contract_start_date: string | null
  contract_end_date: string | null
  signature_date: string | null
}

export interface BatchContractRequest extends ContractRequest {
  teacher_cis?: string[] | null  // null = all teachers
}

export interface ContractFileInfo {
  teacher_ci: string
  teacher_name: string
  filename: string
  file_size: number
  public_id?: string | null
  document_kind?: 'original' | 'amendment' | null
  version?: number | null
  download_url?: string | null
}

export interface BatchContractResponse {
  total_generated: number
  contracts: ContractFileInfo[]
  zip_filename: string
  errors: string[]
}

export interface ContractListItem {
  filename: string
  file_size: number
  created_at: number
}

export interface ContractLine {
  line_number: number
  activity_kind: 'theory' | 'practice'
  rate_class: 'regular' | 'practice'
  hourly_rate: number
  hours: number
  hour_basis: 'weekly' | 'payable'
  subject_label: string
  group_label: string
  semester_label: string
  schedule_label: string
  effective_from: string
  effective_to: string
  source_kind: 'legacy' | 'published'
  source_id: number
  change_kind: 'full' | 'added' | 'removed' | 'changed'
  previous_hours: number | null
  previous_hourly_rate: number | null
}

export interface ContractDocument {
  id: number
  public_id: string
  teacher_ci: string
  teacher_name: string
  academic_period: string
  document_kind: 'original' | 'amendment'
  amendment_sequence: number
  version: number
  effective_date: string
  issued_at: string
  source_digest: string
  artifact_sha256: string
  artifact_size: number
  filename: string
  download_url: string
  status: 'issued'
  lines: ContractLine[]
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

export function useGenerateContract() {
  return useMutation({
    mutationFn: async ({
      teacherCi,
      payload,
    }: {
      teacherCi: string
      payload: ContractRequest
    }) => {
      const response = await api.post(
        `/contracts/generate/${teacherCi}`,
        payload,
        { responseType: 'blob' },
      )
      return { blob: response.data as Blob, teacherCi }
    },
    onSuccess: ({ blob, teacherCi }) => {
      const url = window.URL.createObjectURL(new Blob([blob]))
      const link = document.createElement('a')
      link.href = url
      link.download = `Contrato_${teacherCi}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    },
  })
}

export function useContractTerms(teacherCi: string | null, academicPeriod: string | undefined) {
  return useQuery({
    queryKey: ['contract-terms', teacherCi, academicPeriod],
    enabled: Boolean(teacherCi && academicPeriod),
    queryFn: async (): Promise<ContractTerms> => {
      const response = await api.get<ContractTerms>(`/contracts/terms/${teacherCi}`, {
        params: { academic_period: academicPeriod },
      })
      return response.data
    },
  })
}

export function useIssueContract() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      teacherCi,
      payload,
    }: {
      teacherCi: string
      payload: IssueContractRequest
    }): Promise<ContractDocument> => {
      const response = await api.post<ContractDocument>(`/contracts/issue/${teacherCi}`, payload)
      return response.data
    },
    onSuccess: (_document, { teacherCi }) => {
      void queryClient.invalidateQueries({ queryKey: ['contract-history'] })
      void queryClient.invalidateQueries({ queryKey: ['contract-terms', teacherCi] })
    },
  })
}

export function useGenerateBatchContracts() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: BatchContractRequest): Promise<BatchContractResponse> => {
      const response = await api.post<BatchContractResponse>('/contracts/generate-batch', payload)
      return response.data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['contract-history'] })
    },
  })
}

export function useContractHistory() {
  return useQuery({
    queryKey: ['contract-history'],
    queryFn: async (): Promise<ContractDocument[]> => {
      const response = await api.get<ContractDocument[]>('/contracts/history')
      return response.data
    },
  })
}

export function useListContracts(enabled: boolean = true) {
  return useQuery({
    queryKey: ['contracts-list'],
    queryFn: async (): Promise<ContractListItem[]> => {
      const response = await api.get<ContractListItem[]>('/contracts/list')
      return response.data
    },
    enabled,
  })
}

export async function downloadContract(filename: string): Promise<void> {
  const response = await api.get(`/contracts/download/${filename}`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadContractFile(contract: ContractFileInfo): Promise<void> {
  if (!contract.download_url) {
    await downloadContract(contract.filename)
    return
  }
  const response = await api.get(contract.download_url.replace(/^\/api/, ''), { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
  const link = window.document.createElement('a')
  link.href = url
  link.download = contract.filename
  window.document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadContractDocument(document: ContractDocument): Promise<void> {
  const response = await api.get(document.download_url.replace(/^\/api/, ''), {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
  const link = window.document.createElement('a')
  link.href = url
  link.download = document.filename
  window.document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export async function downloadContractsZip(filenames: string[]): Promise<void> {
  const response = await api.post('/contracts/download-zip', filenames, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(new Blob([response.data as BlobPart]))
  const link = document.createElement('a')
  link.href = url
  link.download = `Contratos_${new Date().toISOString().slice(0, 10)}.zip`
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
