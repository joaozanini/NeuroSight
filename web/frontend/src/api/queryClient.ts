import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './client'

// Repetir não resolve erro do cliente (4xx): só tenta de novo falhas de rede e do servidor.
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: shouldRetry },
      mutations: { retry: false },
    },
  })
}
