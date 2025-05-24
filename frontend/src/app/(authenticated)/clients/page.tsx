'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { apiClient } from '@/lib/api-client'
import { Plus, Edit2, Trash2, Users } from 'lucide-react'

interface Client {
  id: string
  name: string
  code: string
  default_rate: number
  is_active: boolean
  created_at: string
  ticket_count?: number
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingClient, setEditingClient] = useState<Client | null>(null)
  
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    default_rate: ''
  })

  useEffect(() => {
    fetchClients()
  }, [])

  const fetchClients = async () => {
    try {
      const response = await apiClient.get('/api/clients')
      setClients(response.data)
    } catch (error) {
      console.error('Failed to fetch clients:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    try {
      const payload = {
        name: formData.name,
        code: formData.code,
        default_rate: parseFloat(formData.default_rate)
      }

      if (editingClient) {
        await apiClient.put(`/api/clients/${editingClient.id}`, payload)
      } else {
        await apiClient.post('/api/clients', payload)
      }

      await fetchClients()
      resetForm()
    } catch (error) {
      console.error('Failed to save client:', error)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this client?')) return

    try {
      await apiClient.delete(`/api/clients/${id}`)
      await fetchClients()
    } catch (error) {
      console.error('Failed to delete client:', error)
    }
  }

  const startEdit = (client: Client) => {
    setEditingClient(client)
    setFormData({
      name: client.name,
      code: client.code,
      default_rate: client.default_rate.toString()
    })
    setShowAddForm(true)
  }

  const resetForm = () => {
    setFormData({ name: '', code: '', default_rate: '' })
    setEditingClient(null)
    setShowAddForm(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Clients</h1>
          <p className="text-muted-foreground">
            Manage client configurations and rates
          </p>
        </div>
        <Button onClick={() => setShowAddForm(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Client
        </Button>
      </div>

      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingClient ? 'Edit Client' : 'Add New Client'}</CardTitle>
            <CardDescription>
              {editingClient ? 'Update client information' : 'Create a new client configuration'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="name">Client Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="code">Client Code</Label>
                  <Input
                    id="code"
                    value={formData.code}
                    onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                    placeholder="e.g., ABC"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rate">Default Rate</Label>
                  <Input
                    id="rate"
                    type="number"
                    step="0.01"
                    value={formData.default_rate}
                    onChange={(e) => setFormData({ ...formData, default_rate: e.target.value })}
                    placeholder="0.00"
                    required
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit">
                  {editingClient ? 'Update' : 'Create'} Client
                </Button>
                <Button type="button" variant="outline" onClick={resetForm}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {clients.map((client) => (
          <Card key={client.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-lg">{client.name}</CardTitle>
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => startEdit(client)}
                  >
                    <Edit2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(client.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Code:</span>
                <span className="font-medium">{client.code}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Default Rate:</span>
                <span className="font-medium">${client.default_rate.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Status:</span>
                <span className={`font-medium ${client.is_active ? 'text-green-600' : 'text-red-600'}`}>
                  {client.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              {client.ticket_count !== undefined && (
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Tickets:</span>
                  <span className="font-medium">{client.ticket_count.toLocaleString()}</span>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {clients.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No clients found</p>
            <p className="text-sm text-muted-foreground">
              Add your first client to get started
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}