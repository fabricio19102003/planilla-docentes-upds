import { useRef, useState } from 'react'
import { FileText, Upload } from 'lucide-react'

import { Progress, ProgressLabel, ProgressTrack, ProgressIndicator, ProgressValue } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface FileUploaderProps {
  accept: string
  onFileSelect: (file: File) => void
  label: string
  description?: string
  /** Upload progress from 0 to 100. When set, a coss Progress bar replaces the drop hint. */
  progress?: number | null
  /** Label of the progress bar. */
  progressLabel?: string
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileUploader({
  accept,
  onFileSelect,
  label,
  description,
  progress = null,
  progressLabel = 'Subiendo archivo',
}: FileUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const showProgress = progress !== null && progress !== undefined

  const handleFile = (file: File) => {
    setSelectedFile(file)
    onFileSelect(file)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const handleClick = () => {
    inputRef.current?.click()
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors',
        isDragging
          ? 'border-primary bg-primary/10'
          : selectedFile
            ? 'border-primary/40 bg-primary/5'
            : 'border-input hover:border-primary/50 hover:bg-muted/50',
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleInputChange}
      />

      {selectedFile ? (
        <div className="space-y-3">
          <div className="flex items-center justify-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <FileText className="size-[18px]" aria-hidden="true" />
            </div>
            <div className="min-w-0 text-left">
              <p className="max-w-[220px] truncate text-sm font-semibold text-foreground">
                {selectedFile.name}
              </p>
              <p className="text-xs text-muted-foreground tabular-nums">{formatFileSize(selectedFile.size)}</p>
            </div>
          </div>
          {showProgress && (
            <Progress value={progress} onClick={(e) => e.stopPropagation()} className="mx-auto max-w-xs">
              <div className="flex items-center justify-between">
                <ProgressLabel>{progressLabel}</ProgressLabel>
                <ProgressValue />
              </div>
              <ProgressTrack>
                <ProgressIndicator />
              </ProgressTrack>
            </Progress>
          )}
        </div>
      ) : (
        <>
          <div className="mb-3 flex justify-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Upload className="size-[22px]" aria-hidden="true" />
            </div>
          </div>
          <p className="text-sm font-medium text-foreground">{label}</p>
          {description && (
            <p className="mt-1 text-xs text-muted-foreground">{description}</p>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            Arrastrá y soltá o hacé click para seleccionar
          </p>
          <p className="mt-1 text-xs text-muted-foreground/70">Formatos: {accept}</p>
        </>
      )}
    </div>
  )
}
