// Cliente da API. Tudo passa por /api/v1 na mesma origem: no dev, o proxy do Vite leva para o
// FastAPI em :8000; em produção, o próprio FastAPI serve o site. Erros viram ApiError com uma
// mensagem pronta para mostrar, e um 401 manda para o login.

export const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  // Corpo da resposta de erro; nos 422 do FastAPI traz a lista de campos inválidos.
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export const NETWORK_ERROR_MESSAGE = 'Não foi possível falar com o servidor. Verifique a conexão e tente de novo.'
const SERVER_ERROR_MESSAGE = 'O servidor encontrou um erro. Tente de novo em instantes.'
const STATUS_MESSAGES: Record<number, string> = {
  400: 'Não foi possível concluir a operação. Confira os dados e tente de novo.',
  401: 'Sua sessão terminou. Entre de novo para continuar.',
  403: 'Você não tem permissão para fazer isso.',
  404: 'Não encontramos o que você procurou.',
  409: 'A operação conflita com o estado atual. Atualize a página e tente de novo.',
  413: 'O arquivo é grande demais para enviar.',
  422: 'Alguns dados estão inválidos. Confira o formulário.',
}

const AUTH_PATHS = ['/login', '/esqueci-senha', '/redefinir-senha', '/aceitar-convite']

export function isAuthPath(pathname: string): boolean {
  return AUTH_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}

function defaultUnauthorizedHandler() {
  const { pathname, search } = window.location
  if (isAuthPath(pathname)) return
  window.location.assign(`/login?next=${encodeURIComponent(pathname + search)}`)
}

let unauthorizedHandler: () => void = defaultUnauthorizedHandler

// O App registra aqui a navegação do router (sem recarregar a página) e a limpeza do cache.
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler ?? defaultUnauthorizedHandler
}

// Texto de erro para a pessoa: a mensagem do servidor quando ele manda uma (`detail` em texto,
// já em português), senão uma mensagem padrão pelo código HTTP.
export function apiErrorFromResponse(status: number, payload: unknown, redirectOnUnauthorized = true): ApiError {
  if (status === 401 && redirectOnUnauthorized) unauthorizedHandler()
  const detail = payload && typeof payload === 'object' && 'detail' in payload ? (payload as { detail: unknown }).detail : payload
  let message: string
  if (status >= 500) {
    message = SERVER_ERROR_MESSAGE
  } else if (typeof detail === 'string' && detail.trim()) {
    message = detail.charAt(0).toUpperCase() + detail.slice(1)
  } else {
    message = STATUS_MESSAGES[status] ?? STATUS_MESSAGES[400]
  }
  return new ApiError(status, message, detail)
}

export type QueryValue = string | number | boolean | null | undefined

export function buildUrl(path: string, query?: Record<string, QueryValue | QueryValue[]>): string {
  const base = path.startsWith('/api/') ? path : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
  if (!query) return base
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    const values = Array.isArray(value) ? value : [value]
    for (const v of values) if (v !== undefined && v !== null && v !== '') params.append(key, String(v))
  }
  const qs = params.toString()
  return qs ? `${base}?${qs}` : base
}

export function parseBody(text: string): unknown {
  if (!text) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, QueryValue | QueryValue[]>
  // Corpo em JSON; para FormData ou outro corpo use `body`.
  json?: unknown
  body?: BodyInit
  headers?: HeadersInit
  signal?: AbortSignal
  // false quando um 401 é resposta esperada (ex.: login com senha errada).
  redirectOnUnauthorized?: boolean
  responseType?: 'json' | 'blob' | 'text'
}

export async function apiRequest<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, json, body, signal, redirectOnUnauthorized = true, responseType = 'json' } = options
  const headers = new Headers(options.headers)
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  let requestBody = body
  if (json !== undefined) {
    headers.set('Content-Type', 'application/json')
    requestBody = JSON.stringify(json)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), { method, headers, body: requestBody, signal, credentials: 'same-origin' })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, NETWORK_ERROR_MESSAGE)
  }

  if (!response.ok) {
    throw apiErrorFromResponse(response.status, parseBody(await response.text()), redirectOnUnauthorized)
  }
  if (response.status === 204) return undefined as T
  if (responseType === 'blob') return (await response.blob()) as T
  if (responseType === 'text') return (await response.text()) as T
  return parseBody(await response.text()) as T
}

export const api = {
  get: <T = unknown>(path: string, options?: Omit<RequestOptions, 'method' | 'json' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T = unknown>(path: string, json?: unknown, options?: Omit<RequestOptions, 'method' | 'json'>) =>
    apiRequest<T>(path, { ...options, method: 'POST', json }),
  put: <T = unknown>(path: string, json?: unknown, options?: Omit<RequestOptions, 'method' | 'json'>) =>
    apiRequest<T>(path, { ...options, method: 'PUT', json }),
  patch: <T = unknown>(path: string, json?: unknown, options?: Omit<RequestOptions, 'method' | 'json'>) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', json }),
  delete: <T = unknown>(path: string, options?: Omit<RequestOptions, 'method' | 'json' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
}
