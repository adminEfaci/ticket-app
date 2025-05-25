'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { apiClient } from '@/lib/api-client'
import { 
  Search, 
  Plus,
  Edit,
  Trash2,
  Mail, 
  Phone, 
  Building2, 
  DollarSign, 
  FileText,
  TrendingUp,
  Users,
  Package,
  Filter,
  Download,
  Eye,
  Grid3X3,
  List,
  ChevronLeft,
  ChevronRight,
  Calendar,
  CreditCard,
  CheckCircle,
  XCircle,
  MoreVertical,
  Loader2
} from 'lucide-react'
import { useToast } from '@/components/ui/use-toast'
import { format } from 'date-fns'

interface Client {
  id: string
  name: string
  parent_id: string | null
  billing_email: string
  billing_contact_name: string
  billing_phone: string
  invoice_format: string
  invoice_frequency: string
  credit_terms_days: number
  active: boolean
  notes: string
  created_at: string
  updated_at: string
  reference_count?: number
  rate_count?: number
  subcontractor_count?: number
  current_rate?: number
  account_number?: string
  payment_method?: string
}

interface ClientFormData {
  name: string
  parent_id: string | null
  billing_email: string
  billing_contact_name: string
  billing_phone: string
  invoice_format: string
  invoice_frequency: string
  credit_terms_days: number
  active: boolean
  notes: string
}

const defaultFormData: ClientFormData = {
  name: '',
  parent_id: null,
  billing_email: '',
  billing_contact_name: '',
  billing_phone: '',
  invoice_format: 'email',
  invoice_frequency: 'weekly',
  credit_terms_days: 30,
  active: true,
  notes: ''
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [filteredClients, setFilteredClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState<'card' | 'list'>('card')
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage, setItemsPerPage] = useState(20)
  const [selectedClient, setSelectedClient] = useState<Client | null>(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [formData, setFormData] = useState<ClientFormData>(defaultFormData)
  const [submitting, setSubmitting] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    fetchClients()
  }, [])

  useEffect(() => {
    const filtered = clients.filter(client => 
      client.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      client.billing_email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      client.billing_contact_name.toLowerCase().includes(searchTerm.toLowerCase())
    )
    setFilteredClients(filtered)
    setCurrentPage(1)
  }, [searchTerm, clients])

  const fetchClients = async () => {
    try {
      const response = await apiClient.get('/api/clients/with-rates')
      // Extract account number from notes
      const clientsWithExtras = response.data.map((client: Client) => {
        // Extract account number from notes
        const accountMatch = client.notes?.match(/Account Number:\s*(\d+)/i)
        const accountNumber = accountMatch ? accountMatch[1] : null
        
        // Extract payment method from notes
        const paymentMatch = client.notes?.match(/Payment Method:\s*([A-Z]+)/i)
        const paymentMethod = paymentMatch ? paymentMatch[1] : null
        
        return {
          ...client,
          account_number: accountNumber,
          payment_method: paymentMethod,
        }
      })
      
      // Sort by account number
      const sorted = clientsWithExtras.sort((a: Client, b: Client) => {
        const aNum = parseInt(a.account_number || '999999')
        const bNum = parseInt(b.account_number || '999999')
        return aNum - bNum
      })
      
      setClients(sorted)
      setFilteredClients(sorted)
    } catch (error) {
      console.error('Failed to fetch clients:', error)
      toast({
        title: 'Error',
        description: 'Failed to load clients',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    setSubmitting(true)
    try {
      await apiClient.post('/api/clients', formData)
      toast({
        title: 'Success',
        description: 'Client created successfully'
      })
      setIsCreateOpen(false)
      setFormData(defaultFormData)
      await fetchClients()
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to create client',
        variant: 'destructive'
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleUpdate = async () => {
    if (!selectedClient) return
    
    setSubmitting(true)
    try {
      await apiClient.put(`/api/clients/${selectedClient.id}`, formData)
      toast({
        title: 'Success',
        description: 'Client updated successfully'
      })
      setIsEditOpen(false)
      await fetchClients()
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to update client',
        variant: 'destructive'
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedClient) return
    
    try {
      await apiClient.delete(`/api/clients/${selectedClient.id}`)
      toast({
        title: 'Success',
        description: 'Client deleted successfully'
      })
      setIsDeleteOpen(false)
      setSelectedClient(null)
      await fetchClients()
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error.response?.data?.detail || 'Failed to delete client',
        variant: 'destructive'
      })
    }
  }

  const openEditDialog = (client: Client) => {
    setSelectedClient(client)
    setFormData({
      name: client.name,
      parent_id: client.parent_id,
      billing_email: client.billing_email,
      billing_contact_name: client.billing_contact_name,
      billing_phone: client.billing_phone,
      invoice_format: client.invoice_format,
      invoice_frequency: client.invoice_frequency,
      credit_terms_days: client.credit_terms_days,
      active: client.active,
      notes: client.notes
    })
    setIsEditOpen(true)
  }

  // Pagination
  const totalPages = Math.ceil(filteredClients.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const currentClients = filteredClients.slice(startIndex, endIndex)

  const ClientForm = () => (
    <div className="space-y-4">
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor="name">Client Name</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Enter client name"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="grid gap-2">
            <Label htmlFor="billing_contact_name">Contact Name</Label>
            <Input
              id="billing_contact_name"
              value={formData.billing_contact_name}
              onChange={(e) => setFormData({ ...formData, billing_contact_name: e.target.value })}
              placeholder="Contact person"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="billing_phone">Phone</Label>
            <Input
              id="billing_phone"
              value={formData.billing_phone}
              onChange={(e) => setFormData({ ...formData, billing_phone: e.target.value })}
              placeholder="Phone number"
            />
          </div>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="billing_email">Email</Label>
          <Input
            id="billing_email"
            type="email"
            value={formData.billing_email}
            onChange={(e) => setFormData({ ...formData, billing_email: e.target.value })}
            placeholder="billing@example.com"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="grid gap-2">
            <Label htmlFor="invoice_format">Invoice Format</Label>
            <Select 
              value={formData.invoice_format} 
              onValueChange={(value) => setFormData({ ...formData, invoice_format: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select format" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="pdf">PDF</SelectItem>
                <SelectItem value="print">Print</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="invoice_frequency">Invoice Frequency</Label>
            <Select 
              value={formData.invoice_frequency} 
              onValueChange={(value) => setFormData({ ...formData, invoice_frequency: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select frequency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="biweekly">Bi-weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="credit_terms_days">Credit Terms (Days)</Label>
          <Input
            id="credit_terms_days"
            type="number"
            value={formData.credit_terms_days}
            onChange={(e) => setFormData({ ...formData, credit_terms_days: parseInt(e.target.value) })}
            placeholder="30"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor="notes">Notes</Label>
          <Textarea
            id="notes"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            placeholder="Additional notes..."
            rows={3}
          />
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="active">Active Status</Label>
          <Switch
            id="active"
            checked={formData.active}
            onCheckedChange={(checked) => setFormData({ ...formData, active: checked })}
          />
        </div>
      </div>
    </div>
  )

  const ClientCard = ({ client }: { client: Client }) => (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="h-full hover:shadow-lg transition-shadow cursor-pointer">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="flex items-start justify-between">
                <CardTitle className="text-lg font-semibold">{client.name}</CardTitle>
                {client.account_number && (
                  <Badge variant="outline" className="ml-2">
                    #{client.account_number.padStart(3, '0')}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                {client.active ? (
                  <Badge variant="default" className="text-xs">
                    <CheckCircle className="h-3 w-3 mr-1" />
                    Active
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-xs">
                    <XCircle className="h-3 w-3 mr-1" />
                    Inactive
                  </Badge>
                )}
                {client.current_rate && (
                  <Badge variant="outline" className="text-xs">
                    <DollarSign className="h-3 w-3 mr-1" />
                    ${client.current_rate}/tonne
                  </Badge>
                )}
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="icon"
              className="h-8 w-8"
              onClick={() => {
                setSelectedClient(client)
              }}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Mail className="h-4 w-4" />
              <span className="truncate">{client.billing_email}</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Phone className="h-4 w-4" />
              <span>{client.billing_phone || 'No phone'}</span>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <Users className="h-4 w-4" />
              <span>{client.billing_contact_name}</span>
            </div>
          </div>
          
          <div className="pt-3 border-t">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <CreditCard className="h-3 w-3" />
                <span>{client.credit_terms_days || 10} days</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                <span>{client.invoice_frequency}</span>
              </div>
            </div>
            {client.payment_method && (
              <div className="mt-2 flex items-center gap-1 text-xs">
                <CreditCard className="h-3 w-3" />
                <span className="font-medium">{client.payment_method}</span>
              </div>
            )}
          </div>
          
          <div className="flex gap-2 pt-3">
            <Button 
              variant="outline" 
              size="sm" 
              className="flex-1"
              onClick={() => openEditDialog(client)}
            >
              <Edit className="h-3 w-3 mr-1" />
              Edit
            </Button>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => {
                setSelectedClient(client)
                setIsDeleteOpen(true)
              }}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Clients</h1>
          <p className="text-muted-foreground">
            Manage your clients and their billing information
          </p>
        </div>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Client
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>Create New Client</DialogTitle>
              <DialogDescription>
                Add a new client to your system
              </DialogDescription>
            </DialogHeader>
            <ClientForm />
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={submitting}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create Client
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Search and View Controls */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search clients..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={viewMode === 'card' ? 'default' : 'outline'}
            size="icon"
            onClick={() => setViewMode('card')}
          >
            <Grid3X3 className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'outline'}
            size="icon"
            onClick={() => setViewMode('list')}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Client Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Clients</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{clients.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Clients</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {clients.filter(c => c.active).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Weekly Billing</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {clients.filter(c => c.invoice_frequency === 'weekly').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Monthly Billing</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {clients.filter(c => c.invoice_frequency === 'monthly').length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Client List/Grid */}
      {viewMode === 'card' ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence mode="popLayout">
            {currentClients.map((client) => (
              <ClientCard key={client.id} client={client} />
            ))}
          </AnimatePresence>
        </div>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Account</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Rate</TableHead>
                <TableHead>Contact</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Billing</TableHead>
                <TableHead>Payment</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {currentClients.map((client) => (
                <TableRow key={client.id}>
                  <TableCell className="font-mono">
                    {client.account_number ? `#${client.account_number.padStart(3, '0')}` : '-'}
                  </TableCell>
                  <TableCell className="font-medium">{client.name}</TableCell>
                  <TableCell>
                    {client.current_rate ? (
                      <span className="font-medium">${client.current_rate}/t</span>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell>{client.billing_contact_name}</TableCell>
                  <TableCell className="max-w-[200px] truncate">{client.billing_email}</TableCell>
                  <TableCell>{client.billing_phone || '-'}</TableCell>
                  <TableCell>
                    <span className="text-sm">
                      {client.invoice_frequency} / {client.credit_terms_days || 10} days
                    </span>
                  </TableCell>
                  <TableCell>
                    {client.payment_method ? (
                      <Badge variant="outline" className="text-xs">
                        {client.payment_method}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {client.active ? (
                      <Badge variant="default">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(client)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          setSelectedClient(client)
                          setIsDeleteOpen(true)
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <p className="text-sm text-muted-foreground">
              Showing {startIndex + 1} to {Math.min(endIndex, filteredClients.length)} of {filteredClients.length} clients
            </p>
            <Select 
              value={itemsPerPage.toString()} 
              onValueChange={(value) => {
                setItemsPerPage(parseInt(value))
                setCurrentPage(1)
              }}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
                <SelectItem value="200">All</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <Button
                  key={page}
                  variant={currentPage === page ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setCurrentPage(page)}
                  className="w-8"
                >
                  {page}
                </Button>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Edit Client</DialogTitle>
            <DialogDescription>
              Update client information
            </DialogDescription>
          </DialogHeader>
          <ClientForm />
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={submitting}>
              {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Update Client
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={isDeleteOpen} onOpenChange={setIsDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete {selectedClient?.name}. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Delete Client
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}