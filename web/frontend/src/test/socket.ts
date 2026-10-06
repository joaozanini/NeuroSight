// WebSocket falso para as telas ao vivo (W14, W15): guarda as conexões abertas e deixa o teste
// empurrar mensagens do servidor, como o retrato da sessão.
import { act } from '@testing-library/react'
import { vi } from 'vitest'

export class FakeSocket {
  static instances: FakeSocket[] = []
  readonly url: string
  readyState = 0
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeSocket.instances.push(this)
    queueMicrotask(() => {
      this.readyState = 1
      this.onopen?.(new Event('open'))
    })
  }

  close() {
    this.readyState = 3
    this.onclose?.({ code: 1000 })
  }
}

export function mockSockets() {
  FakeSocket.instances = []
  vi.stubGlobal('WebSocket', FakeSocket)
  return {
    // Mensagem do servidor em todas as conexões abertas. O React Query avisa os componentes no
    // tique seguinte, por isso a espera.
    async push(message: unknown) {
      await act(async () => {
        for (const socket of FakeSocket.instances) {
          if (socket.readyState !== 3) socket.onmessage?.({ data: JSON.stringify(message) })
        }
        await new Promise((resolve) => setTimeout(resolve, 0))
      })
    },
    get urls() {
      return FakeSocket.instances.map((s) => s.url)
    },
  }
}
