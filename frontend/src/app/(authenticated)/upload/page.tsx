'use client'

import { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { apiClient } from '@/lib/api-client'
import { 
  Upload, 
  FileSpreadsheet, 
  FileText,
  CheckCircle, 
  XCircle, 
  Loader2, 
  Package, 
  AlertCircle, 
  Calendar, 
  Eye, 
  Play,
  Sparkles,
  Link2,
  FileX,
  Clock,
  Building2
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { format } from 'date-fns'
import { PageWrapper, StaggerChildren, FadeInChild } from '@/components/ui/page-wrapper'
import { getErrorMessage } from '@/lib/error-utils'

interface FilePair {
  xls: File | null
  pdf: File | null
  clientId?: string
}

interface Batch {
  id: string
  description?: string
  file_count?: number
  client_id: string | null
  client_name?: string | null
  status: 'pending' | 'validating' | 'ready' | 'error'
  uploaded_at: string
  xls_filename: string
  pdf_filename: string
  files_info?: Array<{
    filename: string
    file_type: string
    status: string
  }>
}

interface Client {
  id: string
  name: string
}

export default function UploadPage() {
  const [filePairs, setFilePairs] = useState<FilePair[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [selectedClient, setSelectedClient] = useState<string>('')
  const [description, setDescription] = useState('')
  const [uploading, setUploading] = useState(false)
  const [batches, setBatches] = useState<Batch[]>([])
  const [loadingBatches, setLoadingBatches] = useState(true)
  const [viewingBatchId, setViewingBatchId] = useState<string | null>(null)
  const [batchFiles, setBatchFiles] = useState<any>(null)
  const { toast } = useToast()

  useEffect(() => {
    fetchClients()
    fetchBatches()
  }, [])

  const fetchClients = async () => {
    try {
      const response = await apiClient.get('/api/clients/')
      const clientList = Array.isArray(response.data) ? response.data : response.data.items || []
      setClients(clientList)
    } catch (error) {
      console.error('Failed to fetch clients:', error)
    }
  }

  const fetchBatches = async () => {
    try {
      const response = await apiClient.get('/upload/batches')
      setBatches(response.data)
    } catch (error) {
      console.error('Failed to fetch batches:', error)
    } finally {
      setLoadingBatches(false)
    }
  }

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const xlsFiles = acceptedFiles.filter(f => f.name.match(/\.xls$/i))
    const pdfFiles = acceptedFiles.filter(f => f.name.match(/\.pdf$/i))

    const newPairs: FilePair[] = []
    
    xlsFiles.forEach(xlsFile => {
      const baseName = xlsFile.name.replace(/\.xls$/i, '')
      const matchingPdf = pdfFiles.find(pdf => 
        pdf.name.replace(/\.pdf$/i, '').toLowerCase() === baseName.toLowerCase()
      )
      
      newPairs.push({
        xls: xlsFile,
        pdf: matchingPdf || null,
        clientId: selectedClient
      })
    })

    pdfFiles.forEach(pdfFile => {
      if (!newPairs.some(pair => pair.pdf === pdfFile)) {
        const baseName = pdfFile.name.replace(/\.pdf$/i, '')
        const existingPairIndex = filePairs.findIndex(pair => 
          pair.xls && pair.xls.name.replace(/\.xls$/i, '').toLowerCase() === baseName.toLowerCase() && !pair.pdf
        )
        
        if (existingPairIndex >= 0) {
          const updatedPairs = [...filePairs]
          updatedPairs[existingPairIndex].pdf = pdfFile
          setFilePairs(updatedPairs)
        } else {
          newPairs.push({
            xls: null,
            pdf: pdfFile,
            clientId: selectedClient
          })
        }
      }
    })

    setFilePairs(prev => [...prev, ...newPairs])
  }, [filePairs, selectedClient])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.ms-excel': ['.xls'],
      'application/pdf': ['.pdf']
    }
  })

  const removePair = (index: number) => {
    setFilePairs(prev => prev.filter((_, i) => i !== index))
  }

  const uploadFiles = async () => {
    const completePairs = filePairs.filter(pair => pair.xls && pair.pdf)
    
    if (completePairs.length === 0) {
      toast({
        title: 'No complete pairs',
        description: 'Please add both XLS and PDF files for each pair',
        variant: 'destructive'
      })
      return
    }

    setUploading(true)

    try {
      const formData = new FormData()
      
      // Backend expects all files in a single 'files' parameter
      completePairs.forEach((pair, index) => {
        if (pair.xls) formData.append('files', pair.xls)
        if (pair.pdf) formData.append('files', pair.pdf)
      })
      
      if (selectedClient && selectedClient !== 'none' && selectedClient !== '') {
        formData.append('client_id', selectedClient)
      }
      if (description && description.trim() !== '') {
        formData.append('description', description)
      }

      console.log('Uploading files:', {
        fileCount: completePairs.length * 2,
        clientId: selectedClient,
        description: description
      })

      const response = await apiClient.post('/upload/pairs', formData)

      toast({
        title: 'Upload successful',
        description: `Created batch with ${response.data.file_count} files`,
      })

      setFilePairs([])
      setDescription('')
      await fetchBatches()
      
    } catch (error: any) {
      console.error('Upload error:', error)
      console.error('Error response:', JSON.stringify(error.response?.data, null, 2))
      
      const errorDetail = error.response?.data?.detail
      let errorMessage = getErrorMessage(error)
      
      if (errorDetail && typeof errorDetail === 'object') {
        if (errorDetail.message) {
          errorMessage = errorDetail.message
        }
        if (errorDetail.errors) {
          console.error('Detailed errors:', errorDetail.errors)
        }
      }
      
      toast({
        title: 'Upload failed',
        description: errorMessage,
        variant: 'destructive'
      })
    } finally {
      setUploading(false)
    }
  }

  const processBatch = async (batchId: string) => {
    try {
      await apiClient.post(`/batches/${batchId}/parse`)
      toast({
        title: 'Processing started',
        description: 'Batch processing has been initiated',
      })
      await fetchBatches()
    } catch (error: any) {
      console.error('Process batch error:', error)
      console.error('Error response:', JSON.stringify(error.response?.data, null, 2))
      
      toast({
        title: 'Processing failed',
        description: getErrorMessage(error),
        variant: 'destructive'
      })
    }
  }

  const viewBatchFiles = async (batchId: string) => {
    try {
      const response = await apiClient.get(`/upload/batches/${batchId}/files`)
      setBatchFiles(response.data)
      setViewingBatchId(batchId)
    } catch (error: any) {
      toast({
        title: 'Failed to load files',
        description: getErrorMessage(error),
        variant: 'destructive'
      })
    }
  }

  const completePairs = filePairs.filter(pair => pair.xls && pair.pdf)
  const incompletePairs = filePairs.filter(pair => !pair.xls || !pair.pdf)

  return (
    <PageWrapper className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
          Upload Files
        </h1>
        <p className="text-muted-foreground mt-2">
          Upload XLS and PDF file pairs for automated ticket processing
        </p>
      </motion.div>

      {/* Upload Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        <Card className="glass border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              File Upload Center
            </CardTitle>
            <CardDescription>
              Upload matching XLS and PDF files. Files with the same name will be automatically paired.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Client and Description */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="client-select" className="text-base">Client (Optional)</Label>
                <Select value={selectedClient} onValueChange={setSelectedClient}>
                  <SelectTrigger id="client-select" className="h-12 input-modern">
                    <SelectValue placeholder="Select a client" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No specific client</SelectItem>
                    {clients.map(client => (
                      <SelectItem key={client.id} value={client.id}>
                        {client.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description" className="text-base">Description (Optional)</Label>
                <Input
                  id="description"
                  placeholder="Add a description for this batch..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={uploading}
                  className="h-12 input-modern"
                />
              </div>
            </div>

            {/* Dropzone */}
            <motion.div
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              transition={{ type: "spring", stiffness: 400 }}
            >
              <div
                {...getRootProps()}
                className={`relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-300
                  ${isDragActive 
                    ? 'border-primary bg-primary/10 scale-105' 
                    : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-secondary/50'
                  }`}
              >
                <input {...getInputProps()} />
                <motion.div
                  animate={{ 
                    y: isDragActive ? -10 : 0,
                    scale: isDragActive ? 1.1 : 1
                  }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <Upload className="mx-auto h-16 w-16 text-primary/60 mb-4" />
                </motion.div>
                {isDragActive ? (
                  <p className="text-xl font-medium">Drop the files here...</p>
                ) : (
                  <>
                    <p className="text-xl font-medium mb-2">Drag & drop files here</p>
                    <p className="text-muted-foreground">
                      or click to browse your computer
                    </p>
                    <p className="text-sm text-muted-foreground mt-4">
                      Supports XLS and PDF files
                    </p>
                  </>
                )}
              </div>
            </motion.div>

            {/* File Pairs */}
            <AnimatePresence>
              {filePairs.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-lg">
                      File Pairs ({completePairs.length} complete, {incompletePairs.length} incomplete)
                    </h3>
                    <Badge variant="outline" className="text-base">
                      {filePairs.length} total files
                    </Badge>
                  </div>
                  
                  <div className="space-y-3">
                    {completePairs.map((pair, index) => (
                      <motion.div
                        key={`complete-${index}`}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        transition={{ duration: 0.3 }}
                        className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-950/20 rounded-lg border border-green-200 dark:border-green-800"
                      >
                        <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                        <div className="flex items-center gap-2 flex-1">
                          <FileSpreadsheet className="h-5 w-5 text-green-700" />
                          <span className="text-sm font-medium truncate">{pair.xls?.name}</span>
                          <Link2 className="h-4 w-4 text-green-600" />
                          <FileText className="h-5 w-5 text-red-600" />
                          <span className="text-sm font-medium truncate">{pair.pdf?.name}</span>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removePair(filePairs.indexOf(pair))}
                          className="text-destructive hover:text-destructive"
                        >
                          Remove
                        </Button>
                      </motion.div>
                    ))}

                    {incompletePairs.map((pair, index) => (
                      <motion.div
                        key={`incomplete-${index}`}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        transition={{ duration: 0.3 }}
                        className="flex items-center gap-3 p-4 bg-orange-50 dark:bg-orange-950/20 rounded-lg border border-orange-200 dark:border-orange-800"
                      >
                        <AlertCircle className="h-5 w-5 text-orange-600 flex-shrink-0" />
                        <div className="flex items-center gap-2 flex-1">
                          {pair.xls ? (
                            <>
                              <FileSpreadsheet className="h-5 w-5 text-green-700" />
                              <span className="text-sm font-medium truncate">{pair.xls.name}</span>
                              <FileX className="h-4 w-4 text-orange-600" />
                              <span className="text-sm text-orange-600">Missing PDF</span>
                            </>
                          ) : (
                            <>
                              <FileText className="h-5 w-5 text-red-600" />
                              <span className="text-sm font-medium truncate">{pair.pdf?.name}</span>
                              <FileX className="h-4 w-4 text-orange-600" />
                              <span className="text-sm text-orange-600">Missing XLS</span>
                            </>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removePair(filePairs.indexOf(pair))}
                          className="text-destructive hover:text-destructive"
                        >
                          Remove
                        </Button>
                      </motion.div>
                    ))}
                  </div>

                  <div className="flex justify-end pt-4">
                    <Button
                      onClick={uploadFiles}
                      disabled={completePairs.length === 0 || uploading}
                      size="lg"
                      className="button-glow gradient-primary text-white"
                    >
                      {uploading ? (
                        <>
                          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <Upload className="mr-2 h-5 w-5" />
                          Upload {completePairs.length} Pair{completePairs.length !== 1 ? 's' : ''}
                        </>
                      )}
                    </Button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </motion.div>

      {/* Recent Batches */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
      >
        <Card className="glass border-0 shadow-xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-primary" />
              Recent Batches
            </CardTitle>
            <CardDescription>
              View and manage your uploaded file batches
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingBatches ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : batches.length === 0 ? (
              <div className="text-center py-12">
                <Package className="mx-auto h-16 w-16 text-muted-foreground mb-4" />
                <p className="text-lg font-medium mb-2">No batches uploaded yet</p>
                <p className="text-muted-foreground">Upload your first batch to get started</p>
              </div>
            ) : (
              <StaggerChildren className="space-y-4">
                {batches.slice(0, 5).map((batch, index) => (
                  <FadeInChild key={batch.id}>
                    <motion.div
                      whileHover={{ scale: 1.01 }}
                      transition={{ type: "spring", stiffness: 400 }}
                    >
                      <Card className="card-hover">
                        <CardHeader className="pb-3">
                          <div className="flex items-center justify-between">
                            <div className="space-y-1">
                              <CardTitle className="text-lg">
                                {batch.description || `Batch ${batch.id.slice(0, 8)}`}
                              </CardTitle>
                              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {batch.uploaded_at ? 
                                    format(new Date(batch.uploaded_at), 'MMM d, h:mm a') : 
                                    'N/A'
                                  }
                                </span>
                                {batch.client_name && (
                                  <span className="flex items-center gap-1">
                                    <Building2 className="h-3 w-3" />
                                    {batch.client_name}
                                  </span>
                                )}
                              </div>
                            </div>
                            <Badge 
                              variant={
                                batch.status === 'ready' ? 'default' :
                                batch.status === 'validating' ? 'secondary' :
                                batch.status === 'error' ? 'destructive' : 'outline'
                              }
                              className="capitalize"
                            >
                              {batch.status}
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <div className="flex items-center justify-between">
                            <div className="text-sm">
                              <div className="flex items-center gap-2">
                                <FileSpreadsheet className="h-4 w-4 text-green-600" />
                                <span className="text-muted-foreground">{batch.xls_filename}</span>
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <FileText className="h-4 w-4 text-red-600" />
                                <span className="text-muted-foreground">{batch.pdf_filename}</span>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => viewBatchFiles(batch.id)}
                              >
                                <Eye className="mr-2 h-4 w-4" />
                                View
                              </Button>
                              {batch.status === 'pending' && (
                                <Button 
                                  size="sm"
                                  onClick={() => processBatch(batch.id)}
                                  className="gradient-primary text-white"
                                >
                                  <Play className="mr-2 h-4 w-4" />
                                  Process
                                </Button>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  </FadeInChild>
                ))}
              </StaggerChildren>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </PageWrapper>
  )
}