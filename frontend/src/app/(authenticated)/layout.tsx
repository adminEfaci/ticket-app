'use client'

import { ProtectedRoute } from '@/components/auth/protected-route'
import { MainNav } from '@/components/layout/main-nav'

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background">
        <MainNav />
        <main className="container mx-auto px-4 py-8">
          {children}
        </main>
      </div>
    </ProtectedRoute>
  )
}