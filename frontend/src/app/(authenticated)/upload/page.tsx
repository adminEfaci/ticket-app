'use client'

import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient } from '@/lib/api-client'
import { Upload, FileSpreadsheet, FilePdf, CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface UploadedFile {
  file: File
  type: 'xls' | 'pdf'
  status: 'pending' | 'uploading' | 'success' | 'error'
  message?: string
}

export default function UploadPage() {
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [clientName, setClientName] = useState('')
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map(file => {
      const ext = file.name.split('.').pop()?.toLowerCase()
      const type = ext === 'xls' || ext === 'xlsx' ? 'xls' : ext === 'pdf' ? 'pdf' : null
      
      if (!type) {
        return {
          file,
          type: 'xls' as const,
          status: 'error' as const,
          message: 'Invalid file type. Only XLS and PDF files are allowed.'
        }
      }

      return {
        file,
        type,
        status: 'pending' as const
      }
    })

    setFiles(prev => [...prev, ...newFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/pdf': ['.pdf']
    }
  })

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const uploadFiles = async () => {
    if (!clientName.trim()) {
      alert('Please enter a client name')
      return
    }

    setUploading(true)

    for (let i = 0; i < files.length; i++) {
      const uploadFile = files[i]
      if (uploadFile.status !== 'pending') continue

      setFiles(prev => prev.map((f, idx) => 
        idx === i ? { ...f, status: 'uploading' } : f
      ))

      try {
        const formData = new FormData()
        formData.append('file', uploadFile.file)
        formData.append('client_name', clientName)
        formData.append('file_type', uploadFile.type)

        await apiClient.post('/api/upload/file', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })

        setFiles(prev => prev.map((f, idx) => 
          idx === i ? { ...f, status: 'success' } : f
        ))
      } catch (error: any) {
        setFiles(prev => prev.map((f, idx) => 
          idx === i ? { 
            ...f, 
            status: 'error',
            message: error.response?.data?.detail || 'Upload failed'
          } : f
        ))
      }
    }

    setUploading(false)
  }

  const xlsFiles = files.filter(f => f.type === 'xls')
  const pdfFiles = files.filter(f => f.type === 'pdf')
  const pendingFiles = files.filter(f => f.status === 'pending')

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload Files</h1>
        <p className="text-muted-foreground">
          Upload XLS and PDF files for ticket processing
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>File Upload</CardTitle>
          <CardDescription>
            Drag and drop your files or click to browse
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="client">Client Name</Label>
            <Input
              id="client"
              placeholder="Enter client name"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              disabled={uploading}
            />
          </div>

          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
              ${isDragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary'}`}
          >
            <input {...getInputProps()} />
            <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            {isDragActive ? (
              <p className="text-lg">Drop the files here...</p>
            ) : (
              <>
                <p className="text-lg">Drag & drop files here, or click to select</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Supports XLS, XLSX, and PDF files
                </p>
              </>
            )}
          </div>

          {files.length > 0 && (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileSpreadsheet className="h-4 w-4" />
                      Excel Files ({xlsFiles.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {xlsFiles.map((file, index) => (
                      <FileItem
                        key={index}
                        file={file}
                        onRemove={() => removeFile(files.indexOf(file))}
                        disabled={uploading}
                      />
                    ))}
                    {xlsFiles.length === 0 && (
                      <p className="text-sm text-muted-foreground">No Excel files uploaded</p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FilePdf className="h-4 w-4" />
                      PDF Files ({pdfFiles.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {pdfFiles.map((file, index) => (
                      <FileItem
                        key={index}
                        file={file}
                        onRemove={() => removeFile(files.indexOf(file))}
                        disabled={uploading}
                      />
                    ))}
                    {pdfFiles.length === 0 && (
                      <p className="text-sm text-muted-foreground">No PDF files uploaded</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={uploadFiles}
                  disabled={!clientName.trim() || pendingFiles.length === 0 || uploading}
                >
                  {uploading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    `Upload ${pendingFiles.length} file${pendingFiles.length !== 1 ? 's' : ''}`
                  )}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function FileItem({ 
  file, 
  onRemove, 
  disabled 
}: { 
  file: UploadedFile
  onRemove: () => void
  disabled: boolean 
}) {
  return (
    <div className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {file.status === 'uploading' && <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />}
        {file.status === 'success' && <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />}
        {file.status === 'error' && <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />}
        {file.status === 'pending' && (
          file.type === 'xls' ? 
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground flex-shrink-0" /> :
            <FilePdf className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm truncate">{file.file.name}</p>
          {file.message && (
            <p className="text-xs text-red-500">{file.message}</p>
          )}
        </div>
      </div>
      {file.status === 'pending' && !disabled && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="ml-2"
        >
          Remove
        </Button>
      )}
    </div>
  )
}