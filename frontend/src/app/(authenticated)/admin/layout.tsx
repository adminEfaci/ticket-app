'use client'

import { useAuth } from '@/contexts/auth-context'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import Link from 'next/link'
import { 
  Users, 
  Building2, 
  DollarSign, 
  FileText, 
  Settings,
  BarChart3,
  Shield,
  Database,
  Terminal
} from 'lucide-react'

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { user, loading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && (!user || (user.role !== 'admin' && user.role !== 'manager'))) {
      router.push('/')
    }
  }, [user, loading, router])

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>
  }

  if (!user || (user.role !== 'admin' && user.role !== 'manager')) {
    return null
  }

  const adminMenuItems = [
    { href: '/admin', icon: BarChart3, label: 'Dashboard' },
    { href: '/admin/users', icon: Users, label: 'Users' },
    { href: '/admin/clients', icon: Building2, label: 'Clients' },
    { href: '/admin/rates', icon: DollarSign, label: 'Rates' },
    { href: '/admin/audit', icon: Shield, label: 'Audit Logs' },
    { href: '/admin/batches', icon: Database, label: 'Batches' },
    { href: '/admin/exports', icon: FileText, label: 'Exports' },
    { href: '/admin/terminal', icon: Terminal, label: 'Terminal' },
    { href: '/admin/settings', icon: Settings, label: 'Settings' },
  ]

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="w-64 bg-white shadow-md">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-gray-800">Admin Panel</h2>
          <p className="text-sm text-gray-600 mt-1">
            {user.first_name} {user.last_name} • {user.role}
          </p>
        </div>
        <nav className="mt-6">
          {adminMenuItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center px-6 py-3 text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors"
            >
              <item.icon className="w-5 h-5 mr-3" />
              {item.label}
            </Link>
          ))}
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-8">
          {children}
        </div>
      </div>
    </div>
  )
}