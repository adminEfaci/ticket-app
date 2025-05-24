'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { 
  DollarSign, 
  Clock,
  Check,
  X,
  Filter,
  TrendingUp,
  AlertCircle
} from 'lucide-react'

interface Rate {
  id: string
  client_id: string
  client_name: string
  rate: number
  rate_type: 'per_tonne' | 'fixed'
  effective_from: string
  effective_to: string | null
  status: 'pending' | 'approved' | 'rejected'
  approved_by: string | null
  approved_at: string | null
  created_at: string
  notes: string | null
}

export default function RatesManagement() {
  const [rates, setRates] = useState<Rate[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('pending')
  const [statistics, setStatistics] = useState<any>(null)

  useEffect(() => {
    fetchRates()
  }, [filter])

  const fetchRates = async () => {
    try {
      let endpoint = '/api/clients/rates'
      if (filter === 'pending') {
        endpoint = '/api/clients/rates/pending'
      }
      
      const response = await apiClient.get(endpoint)
      setRates(response.data)
      
      // Fetch statistics
      const statsResponse = await apiClient.get('/api/clients/rates/statistics')
      setStatistics(statsResponse.data)
    } catch (error) {
      console.error('Error fetching rates:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (rateId: string) => {
    try {
      await apiClient.post(`/api/clients/rates/${rateId}/approve`)
      fetchRates()
    } catch (error) {
      console.error('Error approving rate:', error)
    }
  }

  const handleReject = async (rateId: string) => {
    const reason = prompt('Please provide a reason for rejection:')
    if (!reason) return

    try {
      await apiClient.post(`/api/clients/rates/${rateId}/reject`, { reason })
      fetchRates()
    } catch (error) {
      console.error('Error rejecting rate:', error)
    }
  }

  if (loading) {
    return <div>Loading rates...</div>
  }

  const statCards = [
    {
      title: 'Average Rate',
      value: statistics?.average_rate ? `$${statistics.average_rate.toFixed(2)}` : '$0.00',
      subValue: 'per tonne',
      icon: DollarSign,
      color: 'bg-green-500'
    },
    {
      title: 'Pending Approvals',
      value: statistics?.pending_count || 0,
      subValue: 'awaiting review',
      icon: Clock,
      color: 'bg-yellow-500'
    },
    {
      title: 'Total Active Rates',
      value: statistics?.active_count || 0,
      subValue: 'currently effective',
      icon: Check,
      color: 'bg-blue-500'
    },
    {
      title: 'Rate Changes',
      value: statistics?.changes_this_month || 0,
      subValue: 'this month',
      icon: TrendingUp,
      color: 'bg-purple-500'
    }
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Rate Management</h1>
      </div>

      {/* Statistics */}
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

      {/* Filter Tabs */}
      <Card className="p-1 mb-6">
        <div className="flex flex-wrap">
          {(['all', 'pending', 'approved', 'rejected'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                filter === status
                  ? 'bg-primary text-white'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
              {status === 'pending' && rates.length > 0 && (
                <span className="ml-2 bg-yellow-500 text-white text-xs px-2 py-0.5 rounded-full">
                  {rates.length}
                </span>
              )}
            </button>
          ))}
        </div>
      </Card>

      {/* Pending Rates Alert */}
      {filter === 'pending' && rates.length > 0 && (
        <Card className="p-4 mb-6 bg-yellow-50 border-yellow-200">
          <div className="flex items-center space-x-3">
            <AlertCircle className="w-5 h-5 text-yellow-600" />
            <p className="text-sm text-yellow-800">
              You have {rates.length} rate{rates.length > 1 ? 's' : ''} pending approval. 
              Please review and approve or reject them.
            </p>
          </div>
        </Card>
      )}

      {/* Rates List */}
      <div className="space-y-4">
        {rates.length === 0 ? (
          <Card className="p-8 text-center text-gray-500">
            No {filter !== 'all' ? filter : ''} rates found.
          </Card>
        ) : (
          rates.map((rate) => (
            <Card key={rate.id} className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {rate.client_name}
                    </h3>
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full
                      ${rate.status === 'approved' ? 'bg-green-100 text-green-800' : ''}
                      ${rate.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : ''}
                      ${rate.status === 'rejected' ? 'bg-red-100 text-red-800' : ''}
                    `}>
                      {rate.status}
                    </span>
                  </div>
                  
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Rate:</span>
                      <span className="ml-2 font-medium">${rate.rate.toFixed(2)}</span>
                      <span className="text-gray-500 ml-1">
                        {rate.rate_type === 'per_tonne' ? 'per tonne' : 'fixed'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Effective:</span>
                      <span className="ml-2 font-medium">
                        {new Date(rate.effective_from).toLocaleDateString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Created:</span>
                      <span className="ml-2 font-medium">
                        {new Date(rate.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  {rate.notes && (
                    <div className="mt-3 p-3 bg-gray-50 rounded-md">
                      <p className="text-sm text-gray-600">{rate.notes}</p>
                    </div>
                  )}

                  {rate.approved_by && (
                    <div className="mt-2 text-xs text-gray-500">
                      {rate.status === 'approved' ? 'Approved' : 'Rejected'} by {rate.approved_by} on{' '}
                      {new Date(rate.approved_at!).toLocaleString()}
                    </div>
                  )}
                </div>

                {rate.status === 'pending' && (
                  <div className="flex space-x-2 ml-4">
                    <Button
                      size="sm"
                      onClick={() => handleApprove(rate.id)}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      <Check className="w-4 h-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleReject(rate.id)}
                      className="text-red-600 hover:bg-red-50"
                    >
                      <X className="w-4 h-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}