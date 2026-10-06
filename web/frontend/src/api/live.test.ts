import { describe, expect, it } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { keepNewest, liveKeys } from './live'
import type { LiveSnapshot } from './live'

function snapshot(version: number, loaded: number): LiveSnapshot {
  return {
    type: 'live',
    version,
    session_id: 's1',
    status: 'configured',
    started_at: null,
    device: null,
    nearby: [],
    load: { loaded, total: 3, error: null },
    playback: { position: null, neutral: true, paused: false, shown: [] },
  }
}

describe('retrato da sessão ao vivo', () => {
  it('a resposta de uma rota que chega depois do socket não volta o retrato', () => {
    const client = new QueryClient()
    keepNewest(client, snapshot(10, 3)) // pelo socket: tudo carregado
    expect(keepNewest(client, snapshot(9, 0)).load.loaded).toBe(3) // resposta do prepare, mais velha
    expect(client.getQueryData<LiveSnapshot>(liveKeys.snapshot('s1'))?.version).toBe(10)
    expect(keepNewest(client, snapshot(11, 2)).load.loaded).toBe(2)
  })
})
