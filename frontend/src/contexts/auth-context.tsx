'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api-client'

interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  role: 'admin' | 'manager' | 'processor' | 'client'
  is_active: boolean
  created_at: string
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        setLoading(false)
        return
      }

      const response = await apiClient.get('/auth/me')
      setUser(response.data)
    } catch (error) {
      localStorage.removeItem('access_token')
    } finally {
      setLoading(false)
    }
  }

  const login = async (email: string, password: string) => {
    const response = await apiClient.post('/auth/login', {
      email,
      password
    })

    const { access_token, user } = response.data
    localStorage.setItem('access_token', access_token)
    setUser(user)
    router.push('/')
  }

  const logout = async () => {
    await apiClient.post('/auth/logout')
    localStorage.removeItem('access_token')
    setUser(null)
    router.push('/login')
  }

  const register = async (username: string, email: string, password: string) => {
    const response = await apiClient.post('/auth/register', {
      email,
      password,
      first_name: username.split('@')[0],
      last_name: 'User'
    })

    if (response.data.access_token) {
      const { access_token, user } = response.data
      localStorage.setItem('access_token', access_token)
      setUser(user)
      router.push('/')
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}