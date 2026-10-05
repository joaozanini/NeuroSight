import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, apiRequest, buildUrl, isAuthPath, setUnauthorizedHandler } from './client'
import { shouldRetry } from './queryClient'

// Espera a promessa falhar e devolve o erro (falha o teste se ela der certo).
async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    return error as ApiError
  }
  throw new Error('a chamada deveria ter falhado')
}


function jsonResponse(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('cliente da API', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    setUnauthorizedHandler(null)
  })

  it('monta a URL em /api/v1 com a query, ignorando vazios', () => {
    expect(buildUrl('/patients')).toBe('/api/v1/patients')
    expect(buildUrl('patients', { q: 'ana', page: 2, inactive: false, tag: ['a', 'b'], empty: '', none: null })).toBe(
      '/api/v1/patients?q=ana&page=2&inactive=false&tag=a&tag=b',
    )
    expect(buildUrl('/api/v1/sessions/1/video')).toBe('/api/v1/sessions/1/video')
  })

  it('envia JSON e devolve o corpo da resposta', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { id: 'p1' }))
    const data = await api.post<{ id: string }>('/patients', { name: 'Ana' })
    expect(data).toEqual({ id: 'p1' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/patients')
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"name":"Ana"}')
    expect(init.credentials).toBe('same-origin')
    expect((init.headers as Headers).get('Content-Type')).toBe('application/json')
  })

  it('devolve undefined no 204', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    await expect(api.delete('/patients/p1')).resolves.toBeUndefined()
  })

  it('usa a mensagem do servidor (detail em texto)', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: 'sessão não encontrada' }))
    const error = await failure(api.get('/sessions/x'))
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe('Sessão não encontrada')
  })

  it('traduz a validação do FastAPI (422) e guarda os campos', async () => {
    const detail = [{ loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' }]
    fetchMock.mockResolvedValue(jsonResponse(422, { detail }))
    const error = await failure(api.post('/users', {}))
    expect(error.message).toBe('Alguns dados estão inválidos. Confira o formulário.')
    expect(error.detail).toEqual(detail)
  })

  it('não mostra detalhes internos de erro 5xx', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { detail: 'Traceback: KeyError' }))
    const error = await failure(api.get('/x'))
    expect(error.status).toBe(500)
    expect(error.message).toBe('O servidor encontrou um erro. Tente de novo em instantes.')
  })

  it('transforma falha de rede em ApiError com status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const error = await failure(api.get('/x'))
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(0)
    expect(error.message).toMatch(/Não foi possível falar com o servidor/)
  })

  it('deixa passar o cancelamento (AbortError)', async () => {
    fetchMock.mockRejectedValue(new DOMException('cancelado', 'AbortError'))
    await expect(api.get('/x')).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('no 401 chama o redirecionamento para o login', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'não autenticado' }))
    const error = await failure(api.get('/me'))
    expect(handler).toHaveBeenCalledTimes(1)
    expect(error.status).toBe(401)
  })

  it('não redireciona quando o 401 é esperado (login com senha errada)', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'e-mail ou senha incorretos' }))
    const error = await failure(apiRequest('/auth/login', { method: 'POST', json: {}, redirectOnUnauthorized: false }))
    expect(handler).not.toHaveBeenCalled()
    expect(error.message).toBe('E-mail ou senha incorretos')
  })

  it('reconhece as rotas de acesso', () => {
    expect(isAuthPath('/login')).toBe(true)
    expect(isAuthPath('/redefinir-senha')).toBe(true)
    expect(isAuthPath('/pacientes')).toBe(false)
  })
})

describe('repetição das consultas', () => {
  it('não repete erro do cliente e repete até 2 vezes os outros', () => {
    expect(shouldRetry(0, new ApiError(404, 'x'))).toBe(false)
    expect(shouldRetry(0, new ApiError(401, 'x'))).toBe(false)
    expect(shouldRetry(0, new ApiError(500, 'x'))).toBe(true)
    expect(shouldRetry(1, new ApiError(0, 'x'))).toBe(true)
    expect(shouldRetry(2, new ApiError(503, 'x'))).toBe(false)
  })
})
