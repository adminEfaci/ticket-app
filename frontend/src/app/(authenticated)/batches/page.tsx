'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { apiClient } from '@/lib/api-client'
import { 
  Package, 
  Play, 
  Eye, 
  Trash2, 
  FileSpreadsheet, 
  FileText, 
  Calendar,
  AlertCircle,
  CheckCircle,
  Loader2,
  Image as ImageIcon,
  Link as LinkIcon
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { format } from 'date-fns'
import { useRouter } from 'next/navigation'

interface Batch {
  id: string
  description: string
  file_count: number
  client_id: string | null
  client_name: string | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  uploaded_at: string
  created_by: string
  files_info: Array<{
    id: string
    filename: string
    file_type: string
    status: string
    file_hash: string
  }>
  parsing_results?: {
    total_tickets: number
    valid_tickets: number
    invalid_tickets: number
    duplicate_tickets: number
    errors: any[]
  }
  image_extraction_results?: {
    total_images: number
    successful_extractions: number
    failed_extractions: number
  }
}

function BatchStatusBadge({ status }: { status: string }) {
  const variants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline", icon: React.ReactNode }> = {
    pending: { variant: "outline", icon: <AlertCircle className="h-3 w-3" /> },
    processing: { variant: "secondary", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    completed: { variant: "default", icon: <CheckCircle className="h-3 w-3" /> },
    failed: { variant: "destructive", icon: <AlertCircle className="h-3 w-3" /> }
  }
  
  const config = variants[status] || variants.pending
  
  return (
    <Badge variant={config.variant} className="flex items-center gap-1">
      {config.icon}
      {status}
    </Badge>
  )
}

export default function BatchesPage() {
  const [batches, setBatches] = useState<Batch[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedBatch, setSelectedBatch] = useState<Batch | null>(null)
  const [processingBatch, setProcessingBatch] = useState<string | null>(null)
  const { toast } = useToast()
  const router = useRouter()

  useEffect(() => {
    fetchBatches()
  }, [])

  const fetchBatches = async () => {
    try {
      const response = await apiClient.get('/upload/batches')
      setBatches(response.data)
    } catch (error) {
      console.error('Failed to fetch batches:', error)
      toast({
        title: 'Error',
        description: 'Failed to load batches',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const processBatch = async (batchId: string) => {
    setProcessingBatch(batchId)
    try {
      await apiClient.post(`/batches/${batchId}/parse`)
      toast({
        title: 'Processing started',
        description: 'Batch processing has been initiated',
      })
      
      // Poll for updates
      setTimeout(() => fetchBatches(), 2000)
    } catch (error: any) {
      toast({
        title: 'Processing failed',
        description: error.response?.data?.detail || 'Failed to process batch',
        variant: 'destructive'
      })
    } finally {
      setProcessingBatch(null)
    }
  }

  const extractImages = async (batchId: string) => {
    try {
      await apiClient.post(`/batches/${batchId}/extract-images`)
      toast({
        title: 'Image extraction started',
        description: 'Extracting images from PDF files',
      })
      
      setTimeout(() => fetchBatches(), 2000)
    } catch (error: any) {
      toast({
        title: 'Extraction failed',
        description: error.response?.data?.detail || 'Failed to extract images',
        variant: 'destructive'
      })
    }
  }

  const matchTickets = async (batchId: string) => {
    try {
      await apiClient.post(`/match/batches/${batchId}/match`)
      toast({
        title: 'Matching started',
        description: 'Matching tickets to images',
      })
      
      setTimeout(() => fetchBatches(), 2000)
    } catch (error: any) {
      toast({
        title: 'Matching failed',
        description: error.response?.data?.detail || 'Failed to match tickets',
        variant: 'destructive'
      })
    }
  }

  const deleteBatch = async (batchId: string) => {
    if (!confirm('Are you sure you want to delete this batch? This action cannot be undone.')) {
      return
    }

    try {
      await apiClient.delete(`/upload/batches/${batchId}`)
      toast({
        title: 'Batch deleted',
        description: 'The batch has been deleted successfully',
      })
      await fetchBatches()
    } catch (error: any) {
      toast({
        title: 'Delete failed',
        description: error.response?.data?.detail || 'Failed to delete batch',
        variant: 'destructive'
      })
    }
  }


  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Batches</h1>
          <p className="text-muted-foreground">
            Manage and process your uploaded file batches
          </p>
        </div>
        <Button onClick={() => router.push('/upload')}>
          <Package className="mr-2 h-4 w-4" />
          New Batch
        </Button>
      </div>

      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All Batches</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="processing">Processing</TabsTrigger>
          <TabsTrigger value="completed">Completed</TabsTrigger>
          <TabsTrigger value="failed">Failed</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-4">
          <BatchList 
            batches={batches} 
            onProcess={processBatch}
            onExtractImages={extractImages}
            onMatch={matchTickets}
            onDelete={deleteBatch}
            onSelect={setSelectedBatch}
            processingBatch={processingBatch}
          />
        </TabsContent>

        <TabsContent value="pending" className="space-y-4">
          <BatchList 
            batches={batches.filter(b => b.status === 'pending')} 
            onProcess={processBatch}
            onExtractImages={extractImages}
            onMatch={matchTickets}
            onDelete={deleteBatch}
            onSelect={setSelectedBatch}
            processingBatch={processingBatch}
          />
        </TabsContent>

        <TabsContent value="processing" className="space-y-4">
          <BatchList 
            batches={batches.filter(b => b.status === 'processing')} 
            onProcess={processBatch}
            onExtractImages={extractImages}
            onMatch={matchTickets}
            onDelete={deleteBatch}
            onSelect={setSelectedBatch}
            processingBatch={processingBatch}
          />
        </TabsContent>

        <TabsContent value="completed" className="space-y-4">
          <BatchList 
            batches={batches.filter(b => b.status === 'completed')} 
            onProcess={processBatch}
            onExtractImages={extractImages}
            onMatch={matchTickets}
            onDelete={deleteBatch}
            onSelect={setSelectedBatch}
            processingBatch={processingBatch}
          />
        </TabsContent>

        <TabsContent value="failed" className="space-y-4">
          <BatchList 
            batches={batches.filter(b => b.status === 'failed')} 
            onProcess={processBatch}
            onExtractImages={extractImages}
            onMatch={matchTickets}
            onDelete={deleteBatch}
            onSelect={setSelectedBatch}
            processingBatch={processingBatch}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

interface BatchListProps {
  batches: Batch[]
  onProcess: (id: string) => void
  onExtractImages: (id: string) => void
  onMatch: (id: string) => void
  onDelete: (id: string) => void
  onSelect: (batch: Batch) => void
  processingBatch: string | null
}

function BatchList({ batches, onProcess, onExtractImages, onMatch, onDelete, onSelect, processingBatch }: BatchListProps) {
  if (batches.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Package className="h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-lg font-medium">No batches found</p>
          <p className="text-sm text-muted-foreground">
            Upload files to create a new batch
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {batches.map(batch => (
        <Card key={batch.id}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <CardTitle className="text-lg">
                  {batch.description || `Batch ${batch.id.slice(0, 8)}`}
                </CardTitle>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {batch.uploaded_at ? format(new Date(batch.uploaded_at), 'MMM d, yyyy h:mm a') : 'N/A'}
                  </span>
                  {batch.client_name && (
                    <span className="font-medium">{batch.client_name}</span>
                  )}
                  <span>{batch.file_count} files</span>
                </div>
              </div>
              <BatchStatusBadge status={batch.status} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* File breakdown */}
            {batch.files_info && (
              <div className="flex items-center gap-4 text-sm">
                <span className="flex items-center gap-1">
                  <FileSpreadsheet className="h-4 w-4 text-green-600" />
                  {batch.files_info.filter(f => f.file_type === 'xls').length} Excel
                </span>
                <span className="flex items-center gap-1">
                  <FileText className="h-4 w-4 text-red-600" />
                  {batch.files_info.filter(f => f.file_type === 'pdf').length} PDF
                </span>
              </div>
            )}

            {/* Results summary */}
            {batch.parsing_results && (
              <div className="p-3 bg-muted rounded-lg space-y-2">
                <p className="text-sm font-medium">Parsing Results:</p>
                <div className="grid grid-cols-4 gap-2 text-sm">
                  <div>
                    <p className="text-muted-foreground">Total</p>
                    <p className="font-medium">{batch.parsing_results.total_tickets}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Valid</p>
                    <p className="font-medium text-green-600">{batch.parsing_results.valid_tickets}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Invalid</p>
                    <p className="font-medium text-red-600">{batch.parsing_results.invalid_tickets}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Duplicates</p>
                    <p className="font-medium text-orange-600">{batch.parsing_results.duplicate_tickets}</p>
                  </div>
                </div>
              </div>
            )}

            {batch.image_extraction_results && (
              <div className="p-3 bg-muted rounded-lg space-y-2">
                <p className="text-sm font-medium">Image Extraction:</p>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <p className="text-muted-foreground">Total</p>
                    <p className="font-medium">{batch.image_extraction_results.total_images}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Success</p>
                    <p className="font-medium text-green-600">{batch.image_extraction_results.successful_extractions}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Failed</p>
                    <p className="font-medium text-red-600">{batch.image_extraction_results.failed_extractions}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => onSelect(batch)}>
                <Eye className="mr-2 h-4 w-4" />
                View Details
              </Button>
              
              {batch.status === 'pending' && (
                <Button 
                  size="sm" 
                  onClick={() => onProcess(batch.id)}
                  disabled={processingBatch === batch.id}
                >
                  {processingBatch === batch.id ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  Process
                </Button>
              )}

              {batch.status === 'completed' && batch.parsing_results && batch.parsing_results.valid_tickets > 0 && (
                <>
                  <Button size="sm" variant="outline" onClick={() => onExtractImages(batch.id)}>
                    <ImageIcon className="mr-2 h-4 w-4" />
                    Extract Images
                  </Button>
                  {batch.image_extraction_results && batch.image_extraction_results.successful_extractions > 0 && (
                    <Button size="sm" variant="outline" onClick={() => onMatch(batch.id)}>
                      <LinkIcon className="mr-2 h-4 w-4" />
                      Match Tickets
                    </Button>
                  )}
                </>
              )}

              <Button 
                size="sm" 
                variant="ghost" 
                onClick={() => onDelete(batch.id)}
                className="ml-auto text-destructive hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}