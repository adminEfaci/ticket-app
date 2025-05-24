'use client'

import { useEffect, useState } from 'react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { 
  Plus, 
  Search, 
  Edit, 
  Trash2, 
  DollarSign,
  FileUp,
  Download,
  Building2,
  Hash,
  GitBranch
} from 'lucide-react'
import Link from 'next/link'

interface Client {
  id: string
  name: string
  code: string
  active: boolean
  parent_id: string | null
  children: Client[]
  reference_count: number
  rate_count: number
  created_at: string
}

export default function ClientsManagement() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showHierarchy, setShowHierarchy] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)

  useEffect(() => {
    fetchClients()
  }, [])

  const fetchClients = async () => {
    try {
      const response = await apiClient.get('/api/clients/')
      setClients(response.data)
    } catch (error) {
      console.error('Error fetching clients:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (clientId: string) => {
    if (confirm('Are you sure you want to delete this client? This action cannot be undone.')) {
      try {
        await apiClient.delete(`/api/clients/${clientId}`)
        fetchClients()
      } catch (error) {
        console.error('Error deleting client:', error)
      }
    }
  }

  const handleExport = async () => {
    try {
      const response = await apiClient.get('/api/clients/export/csv', {
        responseType: 'blob'
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `clients_${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (error) {
      console.error('Error exporting clients:', error)
    }
  }

  const handleImport = async () => {
    if (!importFile) return

    const formData = new FormData()
    formData.append('file', importFile)

    try {
      await apiClient.post('/api/clients/import/csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      fetchClients()
      setImportFile(null)
    } catch (error) {
      console.error('Error importing clients:', error)
    }
  }

  const filteredClients = clients.filter(client =>
    client.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    client.code.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const ClientRow = ({ client, level = 0 }: { client: Client; level?: number }) => (
    <>
      <tr className="hover:bg-gray-50">
        <td className="px-6 py-4 whitespace-nowrap">
          <div className="flex items-center" style={{ paddingLeft: `${level * 24}px` }}>
            {level > 0 && <GitBranch className="w-4 h-4 text-gray-400 mr-2" />}
            <div>
              <div className="text-sm font-medium text-gray-900">{client.name}</div>
              <div className="text-sm text-gray-500">Code: {client.code}</div>
            </div>
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full
            ${client.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}
          `}>
            {client.active ? 'Active' : 'Inactive'}
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          <div className="flex items-center space-x-4">
            <div className="flex items-center">
              <Hash className="w-4 h-4 text-gray-400 mr-1" />
              {client.reference_count || 0}
            </div>
            <div className="flex items-center">
              <DollarSign className="w-4 h-4 text-gray-400 mr-1" />
              {client.rate_count || 0}
            </div>
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {new Date(client.created_at).toLocaleDateString()}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
          <div className="flex justify-end space-x-2">
            <Link href={`/admin/clients/${client.id}/edit`}>
              <Button variant="ghost" size="sm">
                <Edit className="w-4 h-4" />
              </Button>
            </Link>
            <Link href={`/admin/clients/${client.id}/references`}>
              <Button variant="ghost" size="sm">
                <Hash className="w-4 h-4" />
              </Button>
            </Link>
            <Link href={`/admin/clients/${client.id}/rates`}>
              <Button variant="ghost" size="sm">
                <DollarSign className="w-4 h-4" />
              </Button>
            </Link>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleDelete(client.id)}
            >
              <Trash2 className="w-4 h-4 text-red-600" />
            </Button>
          </div>
        </td>
      </tr>
      {showHierarchy && client.children?.map(child => (
        <ClientRow key={child.id} client={child} level={level + 1} />
      ))}
    </>
  )

  if (loading) {
    return <div>Loading clients...</div>
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Client Management</h1>
        <div className="flex space-x-3">
          <Button
            onClick={handleExport}
            variant="outline"
            className="flex items-center space-x-2"
          >
            <Download className="w-4 h-4" />
            <span>Export</span>
          </Button>
          <Link href="/admin/clients/new">
            <Button className="flex items-center space-x-2">
              <Plus className="w-4 h-4" />
              <span>Add Client</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Import Section */}
      <Card className="p-4 mb-6">
        <div className="flex items-center space-x-4">
          <Building2 className="w-5 h-5 text-gray-500" />
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-700">Bulk Import Clients</p>
            <p className="text-xs text-gray-500">Upload a CSV file to import multiple clients</p>
          </div>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => setImportFile(e.target.files?.[0] || null)}
            className="text-sm"
          />
          <Button
            onClick={handleImport}
            disabled={!importFile}
            size="sm"
            className="flex items-center space-x-2"
          >
            <FileUp className="w-4 h-4" />
            <span>Import</span>
          </Button>
        </div>
      </Card>

      {/* Search and Filters */}
      <Card className="p-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search clients..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center space-x-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={showHierarchy}
                onChange={(e) => setShowHierarchy(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Show Hierarchy</span>
            </label>
            <span className="text-sm text-gray-600">
              {filteredClients.length} clients
            </span>
          </div>
        </div>
      </Card>

      {/* Clients Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Client
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  References / Rates
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredClients.map((client) => (
                <ClientRow key={client.id} client={client} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}