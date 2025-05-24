'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api-client'
import { Card } from '@/components/ui/card'
import { 
  Users, 
  Building2, 
  FileText, 
  TrendingUp,
  Activity,
  DollarSign,
  Package,
  AlertCircle
} from 'lucide-react'

interface DashboardStats {
  totalUsers: number
  activeUsers: number
  totalClients: number
  activeClients: number
  totalTickets: number
  pendingBatches: number
  weeklyRevenue: number
  pendingRates: number
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [recentActivity, setRecentActivity] = useState<any[]>([])

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      // Fetch various statistics
      const [usersRes, clientsRes, batchesRes, ratesRes] = await Promise.all([
        apiClient.get('/api/users/'),
        apiClient.get('/api/clients/'),
        apiClient.get('/api/batches/'),
        apiClient.get('/api/clients/rates/pending')
      ])

      const users = usersRes.data
      const clients = clientsRes.data
      const batches = batchesRes.data
      const pendingRates = ratesRes.data

      setStats({
        totalUsers: users.length,
        activeUsers: users.filter((u: any) => u.is_active).length,
        totalClients: clients.length,
        activeClients: clients.filter((c: any) => c.active).length,
        totalTickets: batches.reduce((acc: number, b: any) => acc + (b.ticket_count || 0), 0),
        pendingBatches: batches.filter((b: any) => b.status === 'pending').length,
        weeklyRevenue: 0, // Calculate from recent exports
        pendingRates: pendingRates.length
      })

      // Fetch recent audit logs if available
      try {
        const auditRes = await apiClient.get('/api/audit/recent?limit=10')
        setRecentActivity(auditRes.data)
      } catch (e) {
        // Audit endpoint might not be implemented yet
      }

    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div>Loading dashboard...</div>
  }

  const statCards = [
    {
      title: 'Total Users',
      value: stats?.totalUsers || 0,
      subValue: `${stats?.activeUsers || 0} active`,
      icon: Users,
      color: 'bg-blue-500'
    },
    {
      title: 'Total Clients',
      value: stats?.totalClients || 0,
      subValue: `${stats?.activeClients || 0} active`,
      icon: Building2,
      color: 'bg-green-500'
    },
    {
      title: 'Total Tickets',
      value: stats?.totalTickets || 0,
      subValue: `${stats?.pendingBatches || 0} pending batches`,
      icon: FileText,
      color: 'bg-purple-500'
    },
    {
      title: 'Pending Rates',
      value: stats?.pendingRates || 0,
      subValue: 'Awaiting approval',
      icon: DollarSign,
      color: 'bg-yellow-500'
    }
  ]

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Admin Dashboard</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => (
          <Card key={index} className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">{stat.title}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
                <p className="text-xs text-gray-500 mt-1">{stat.subValue}</p>
              </div>
              <div className={`${stat.color} p-3 rounded-lg`}>
                <stat.icon className="w-6 h-6 text-white" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-4 hover:shadow-lg transition-shadow cursor-pointer">
            <a href="/admin/users/new" className="flex items-center space-x-3">
              <Users className="w-5 h-5 text-blue-500" />
              <span>Create New User</span>
            </a>
          </Card>
          <Card className="p-4 hover:shadow-lg transition-shadow cursor-pointer">
            <a href="/admin/clients/new" className="flex items-center space-x-3">
              <Building2 className="w-5 h-5 text-green-500" />
              <span>Add New Client</span>
            </a>
          </Card>
          <Card className="p-4 hover:shadow-lg transition-shadow cursor-pointer">
            <a href="/admin/exports" className="flex items-center space-x-3">
              <Package className="w-5 h-5 text-purple-500" />
              <span>Generate Export</span>
            </a>
          </Card>
        </div>
      </div>

      {/* Recent Activity */}
      {recentActivity.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Activity</h2>
          <Card className="p-6">
            <div className="space-y-4">
              {recentActivity.map((activity, index) => (
                <div key={index} className="flex items-center space-x-3 pb-3 border-b last:border-0">
                  <Activity className="w-4 h-4 text-gray-400" />
                  <div className="flex-1">
                    <p className="text-sm text-gray-900">{activity.action}</p>
                    <p className="text-xs text-gray-500">
                      {activity.user_email} • {new Date(activity.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Alerts */}
      {stats && stats.pendingRates > 0 && (
        <div className="mt-8">
          <Card className="p-4 bg-yellow-50 border-yellow-200">
            <div className="flex items-center space-x-3">
              <AlertCircle className="w-5 h-5 text-yellow-600" />
              <p className="text-sm text-yellow-800">
                You have {stats.pendingRates} pending rate{stats.pendingRates > 1 ? 's' : ''} awaiting approval.
                <a href="/admin/rates" className="ml-2 underline font-medium">Review now →</a>
              </p>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}