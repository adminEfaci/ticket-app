'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient } from '@/lib/api-client'
import { Download, Calendar, FileSpreadsheet, Package, CheckCircle } from 'lucide-react'
import { format } from 'date-fns'

interface ExportResult {
  bundle_path: string
  stats: {
    total_tickets: number
    total_weeks: number
    total_clients: number
    total_references: number
  }
  validation: {
    is_valid: boolean
    errors: string[]
    warnings: string[]
  }
}

export default function ExportPage() {
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [exporting, setExporting] = useState(false)
  const [result, setResult] = useState<ExportResult | null>(null)
  const [error, setError] = useState('')

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setExporting(true)

    try {
      const response = await apiClient.post('/api/export/weekly', {
        start_date: startDate,
        end_date: endDate,
        export_type: 'weekly'
      })

      setResult(response.data)
      
      // Download the file
      if (response.data.bundle_path) {
        const downloadResponse = await apiClient.get(`/api/export/download/${response.data.bundle_path}`, {
          responseType: 'blob'
        })
        
        const url = window.URL.createObjectURL(new Blob([downloadResponse.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', response.data.bundle_path)
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const today = format(new Date(), 'yyyy-MM-dd')
  const lastWeek = format(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd')

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Export Data</h1>
        <p className="text-muted-foreground">
          Generate weekly export bundles for REPRINT tickets
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Export Settings</CardTitle>
            <CardDescription>
              Select the date range for your export
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleExport} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="start-date">Start Date</Label>
                  <Input
                    id="start-date"
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    max={today}
                    required
                    disabled={exporting}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end-date">End Date</Label>
                  <Input
                    id="end-date"
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    min={startDate}
                    max={today}
                    required
                    disabled={exporting}
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 text-sm text-red-500 bg-red-50 rounded-md">
                  {error}
                </div>
              )}

              <div className="flex gap-2">
                <Button type="submit" disabled={exporting}>
                  {exporting ? (
                    <>
                      <Download className="mr-2 h-4 w-4 animate-pulse" />
                      Generating Export...
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      Generate Export
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setStartDate(lastWeek)
                    setEndDate(today)
                  }}
                >
                  <Calendar className="mr-2 h-4 w-4" />
                  Last 7 Days
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Export Information</CardTitle>
            <CardDescription>
              What's included in the export
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3">
              <FileSpreadsheet className="h-5 w-5 text-primary mt-0.5" />
              <div>
                <p className="font-medium">Weekly Grouping</p>
                <p className="text-sm text-muted-foreground">
                  Tickets grouped by Monday-Saturday weeks
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Package className="h-5 w-5 text-primary mt-0.5" />
              <div>
                <p className="font-medium">Hierarchical Structure</p>
                <p className="text-sm text-muted-foreground">
                  Organized by Week → Client → Reference Number
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-primary mt-0.5" />
              <div>
                <p className="font-medium">Complete Validation</p>
                <p className="text-sm text-muted-foreground">
                  Financial accuracy with 2-decimal precision
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {result && (
        <Card className={result.validation.is_valid ? 'border-green-500' : 'border-yellow-500'}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {result.validation.is_valid ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  Export Completed Successfully
                </>
              ) : (
                <>
                  <CheckCircle className="h-5 w-5 text-yellow-500" />
                  Export Completed with Warnings
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Tickets</p>
                <p className="text-2xl font-bold">{result.stats.total_tickets}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Weeks</p>
                <p className="text-2xl font-bold">{result.stats.total_weeks}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Clients</p>
                <p className="text-2xl font-bold">{result.stats.total_clients}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">References</p>
                <p className="text-2xl font-bold">{result.stats.total_references}</p>
              </div>
            </div>

            {result.validation.errors.length > 0 && (
              <div className="space-y-2">
                <p className="font-medium text-red-600">Errors:</p>
                <ul className="list-disc list-inside text-sm text-red-600 space-y-1">
                  {result.validation.errors.map((error, idx) => (
                    <li key={idx}>{error}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.validation.warnings.length > 0 && (
              <div className="space-y-2">
                <p className="font-medium text-yellow-600">Warnings:</p>
                <ul className="list-disc list-inside text-sm text-yellow-600 space-y-1">
                  {result.validation.warnings.map((warning, idx) => (
                    <li key={idx}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}