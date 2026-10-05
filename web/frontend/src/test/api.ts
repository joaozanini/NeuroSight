// API falsa para os testes de tela: cada rota ("GET /users/:id") responde um valor fixo ou uma
// função. O que não estiver mapeado responde 404, como o servidor.
import { vi } from 'vitest'

export interface ApiCall {
  method: string
  path: string
  query: URLSearchParams
  body: unknown
}

export type RouteCall = ApiCall & { params: Record<string, string> }

// Resposta fixa (objeto, Response, ou undefined para 204) ou função que monta a resposta.
type Handler = ((call: RouteCall) => unknown) | object | string | number | boolean | null | undefined

export function reply(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function compile(route: string) {
  const [method, pattern] = route.split(' ')
  const names: string[] = []
  const regex = new RegExp(
    `^${pattern.replace(/:([a-zA-Z]+)/g, (_, name: string) => {
      names.push(name)
      return '([^/]+)'
    })}$`,
  )
  return { method, regex, names }
}

export function mockApi(routes: Record<string, Handler>) {
  const compiled = Object.entries(routes).map(([route, handler]) => ({ ...compile(route), handler }))
  const calls: ApiCall[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const method = init?.method ?? 'GET'
    const path = url.pathname.replace(/^\/api\/v1/, '')
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    const call = { method, path, query: url.searchParams, body }
    calls.push(call)
    for (const route of compiled) {
      const m = route.method === method ? route.regex.exec(path) : null
      if (!m) continue
      const params = Object.fromEntries(route.names.map((name, i) => [name, decodeURIComponent(m[i + 1])]))
      const result = typeof route.handler === 'function' ? await (route.handler as (c: RouteCall) => unknown)({ ...call, params }) : route.handler
      if (result instanceof Response) return result
      return result === undefined ? new Response(null, { status: 204 }) : reply(200, result)
    }
    return reply(404, { detail: 'rota não encontrada' })
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    calls,
    // Chamadas a uma rota ("PATCH /users/u2").
    callsTo: (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path),
  }
}
