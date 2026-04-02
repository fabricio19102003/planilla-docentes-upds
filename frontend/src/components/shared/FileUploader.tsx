import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'

interface FileUploaderProps {
  accept: string
  onFileSelect: (file: File) => void
  label: string
  description?: string
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function FileUploader({ accept, onFileSelect, label, description }: FileUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

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
      className={[
        'border-2 border-dashed rounded-lg p-6 cursor-pointer transition-colors text-center',
        isDragging
          ? 'bg-sky-50 border-[#4DA8DA]'
          : selectedFile
          ? 'bg-blue-50 border-[#0066CC]'
          : 'border-[#4DA8DA] hover:bg-sky-50 hover:border-[#0066CC]',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={handleInputChange}
      />

      {selectedFile ? (
        <div className="flex items-center justify-center gap-3">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ backgroundColor: 'rgba(0,102,204,0.12)' }}
          >
            <Upload size={18} style={{ color: '#0066CC' }} />
          </div>
          <div className="text-left">
            <p className="text-sm font-semibold text-gray-700 truncate max-w-[220px]">
              {selectedFile.name}
            </p>
            <p className="text-xs text-gray-400">{formatFileSize(selectedFile.size)}</p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex justify-center mb-3">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(77,168,218,0.15)' }}
            >
              <Upload size={22} style={{ color: '#4DA8DA' }} />
            </div>
          </div>
          <p className="text-sm font-medium text-gray-700">{label}</p>
          {description && (
            <p className="text-xs text-gray-400 mt-1">{description}</p>
          )}
          <p className="text-xs text-gray-400 mt-2">
            Arrastrá y soltá o hacé click para seleccionar
          </p>
          <p className="text-xs text-gray-300 mt-1">Formatos: {accept}</p>
        </>
      )}
    </div>
  )
}
