'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { apiClient } from '@/lib/api-client'
import { FileSpreadsheet, Upload, Users, Download, CheckCircle, XCircle, Clock } from 'lucide-react'

interface DashboardStats {
  total_tickets: number
  total_matches: number
  match_rate: number
  total_clients: number
  recent_uploads: number
  pending_reviews: number
  processing_errors: number
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const response = await apiClient.get('/api/dashboard/stats')
      setStats(response.data)
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  const defaultStats: DashboardStats = stats || {
    total_tickets: 0,
    total_matches: 0,
    match_rate: 0,
    total_clients: 0,
    recent_uploads: 0,
    pending_reviews: 0,
    processing_errors: 0,
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your ticket processing system
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Tickets</CardTitle>
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{defaultStats.total_tickets.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              Processed all time
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Match Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{defaultStats.match_rate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">
              {defaultStats.total_matches.toLocaleString()} successful matches
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Clients</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{defaultStats.total_clients}</div>
            <p className="text-xs text-muted-foreground">
              Registered clients
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recent Uploads</CardTitle>
            <Upload className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{defaultStats.recent_uploads}</div>
            <p className="text-xs text-muted-foreground">
              Last 7 days
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Reviews</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{defaultStats.pending_reviews}</div>
            <p className="text-xs text-muted-foreground">
              Awaiting manual review
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Processing Errors</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{defaultStats.processing_errors}</div>
            <p className="text-xs text-muted-foreground">
              Requires attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Export Ready</CardTitle>
            <Download className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">Weekly</div>
            <p className="text-xs text-muted-foreground">
              Export available for current week
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
          <CardDescription>
            Common tasks and operations
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <a href="/upload" className="block">
            <Card className="cursor-pointer hover:bg-accent transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-center space-x-2">
                  <Upload className="h-5 w-5 text-primary" />
                  <CardTitle className="text-sm">Upload Files</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Upload XLS and PDF files for processing
                </p>
              </CardContent>
            </Card>
          </a>

          <a href="/export" className="block">
            <Card className="cursor-pointer hover:bg-accent transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-center space-x-2">
                  <Download className="h-5 w-5 text-primary" />
                  <CardTitle className="text-sm">Export Data</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Generate weekly export bundles
                </p>
              </CardContent>
            </Card>
          </a>

          <a href="/clients" className="block">
            <Card className="cursor-pointer hover:bg-accent transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-center space-x-2">
                  <Users className="h-5 w-5 text-primary" />
                  <CardTitle className="text-sm">Manage Clients</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  View and manage client configurations
                </p>
              </CardContent>
            </Card>
          </a>

          <a href="/review" className="block">
            <Card className="cursor-pointer hover:bg-accent transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-5 w-5 text-primary" />
                  <CardTitle className="text-sm">Review Queue</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Review and approve pending matches
                </p>
              </CardContent>
            </Card>
          </a>
        </CardContent>
      </Card>
    </div>
  )
}