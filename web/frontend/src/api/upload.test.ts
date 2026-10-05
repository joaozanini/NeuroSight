import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, setUnauthorizedHandler } from './client'
import { uploadFile } from './upload'

// Espera a promessa falhar e devolve o erro (falha o teste se ela der certo).
async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    return error as ApiError
  }
  throw new Error('a chamada deveria ter falhado')
}


// XHR falso: guarda o que foi enviado e deixa o teste disparar progresso e resposta.
class FakeXhr {
  static last: FakeXhr
  method = ''
  url = ''
  headers: Record<string, string> = {}
  body: FormData | null = null
  status = 0
  responseText = ''
  upload: { onprogress: ((e: ProgressEvent) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  aborted = false

  constructor() {
    FakeXhr.last = this
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send(body: FormData) {
    this.body = body
  }
  abort() {
    this.aborted = true
    this.onabort?.()
  }
  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total } as ProgressEvent)
  }
  respond(status: number, body: unknown) {
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

describe('envio com progresso (XHR)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    setUnauthorizedHandler(null)
  })

  it('envia o arquivo em multipart e informa o progresso', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    const onProgress = vi.fn()
    const file = new File(['x'.repeat(100)], 'cachoeira.jpg', { type: 'image/jpeg' })
    const promise = uploadFile<{ id: string }>('/stimuli', { file, fields: { kind: 'image' }, onProgress })

    const xhr = FakeXhr.last
    expect(xhr.method).toBe('POST')
    expect(xhr.url).toBe('/api/v1/stimuli')
    expect((xhr.body!.get('file') as File).name).toBe('cachoeira.jpg')
    expect(xhr.body!.get('kind')).toBe('image')

    xhr.progress(64, 100)
    expect(onProgress).toHaveBeenLastCalledWith({ loaded: 64, total: 100, fraction: 0.64 })
    xhr.respond(201, { id: 's1' })
    await expect(promise).resolves.toEqual({ id: 's1' })
    expect(onProgress).toHaveBeenLastCalledWith({ loaded: 100, total: 100, fraction: 1 })
  })

  it('rejeita com ApiError e a mensagem do servidor', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    const promise = uploadFile('/stimuli', { file: new Blob(['x']), fileName: 'video.mov' })
    FakeXhr.last.respond(415, { detail: 'formato não aceito' })
    const error = await failure(promise)
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(415)
    expect(error.message).toBe('Formato não aceito')
  })

  it('leva ao login no 401', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    const promise = uploadFile('/stimuli', { file: new Blob(['x']) })
    FakeXhr.last.respond(401, { detail: 'não autenticado' })
    await promise.catch(() => undefined)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('cancela pelo AbortSignal', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    const controller = new AbortController()
    const promise = uploadFile('/stimuli', { file: new Blob(['x']), signal: controller.signal })
    controller.abort()
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
    expect(FakeXhr.last.aborted).toBe(true)
  })

  it('falha de rede vira ApiError com status 0', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    const promise = uploadFile('/stimuli', { file: new Blob(['x']) })
    FakeXhr.last.onerror?.()
    await expect(promise).rejects.toMatchObject({ status: 0 })
  })
})
