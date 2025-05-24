import { renderHook } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/auth-context'
import { ReactNode } from 'react'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
}))

// Mock API client
jest.mock('@/lib/api-client', () => ({
  apiClient: {
    get: jest.fn(() => Promise.reject(new Error('No auth'))),
    post: jest.fn(),
  }
}))

describe('AuthContext Basic Tests', () => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  )

  it('provides auth context', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    
    expect(result.current).toBeDefined()
    expect(result.current.login).toBeDefined()
    expect(result.current.logout).toBeDefined()
    expect(result.current.register).toBeDefined()
  })

  it('throws error when used outside provider', () => {
    const originalError = console.error
    console.error = jest.fn()

    expect(() => {
      renderHook(() => useAuth())
    }).toThrow('useAuth must be used within an AuthProvider')

    console.error = originalError
  })
})