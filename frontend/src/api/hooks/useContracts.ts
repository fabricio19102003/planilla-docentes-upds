import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ContractRequest {
  department: string
  duration_text: string
  start_date: string
  end_date: string
  hourly_rate: string
  hourly_rate_literal: string
}

export interface BatchContractRequest extends ContractRequest {
  teacher_cis?: string[] | null  // null = all teachers
}

export interface ContractFileInfo {
  teacher_ci: string
  teacher_name: string
  filename: string
  file_size: number
}

export interface BatchContractResponse {
  total_generated: number
  contracts: ContractFileInfo[]
  zip_filename: string
}

export interface ContractListItem {
  filename: string
  file_size: number
  created_at: number
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

export function useGenerateBatchContracts() {
  return useMutation({
    mutationFn: async (payload: BatchContractRequest): Promise<BatchContractResponse> => {
      const response = await api.post<BatchContractResponse>('/contracts/generate-batch', payload)
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
