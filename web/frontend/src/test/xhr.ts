// XHR falso para os envios com progresso (uploadFile): guarda o que foi enviado e deixa o teste
// disparar progresso e resposta. `all` tem todos os envios, na ordem em que começaram.
export class FakeXhr {
  static last: FakeXhr
  static all: FakeXhr[] = []
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
    FakeXhr.all.push(this)
  }
  static reset() {
    FakeXhr.all = []
  }
  // O envio de um arquivo pelo nome.
  static of(fileName: string): FakeXhr {
    const found = FakeXhr.all.find((x) => (x.body?.get('file') as File | null)?.name === fileName)
    if (!found) throw new Error(`nenhum envio de ${fileName}`)
    return found
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
