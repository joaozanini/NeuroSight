// Envio de arquivo com progresso. O fetch não informa o progresso do upload, por isso o XHR.
import { ApiError, NETWORK_ERROR_MESSAGE, apiErrorFromResponse, buildUrl, parseBody } from './client'

export interface UploadProgress {
  loaded: number
  total: number
  // De 0 a 1.
  fraction: number
}

export interface UploadOptions {
  file: Blob
  fileName?: string
  // Nome do campo do arquivo no multipart.
  fieldName?: string
  // Outros campos do formulário enviados junto.
  fields?: Record<string, string>
  method?: 'POST' | 'PUT'
  onProgress?: (progress: UploadProgress) => void
  signal?: AbortSignal
}

export function uploadFile<T = unknown>(path: string, options: UploadOptions): Promise<T> {
  const { file, fileName, fieldName = 'file', fields, method = 'POST', onProgress, signal } = options

  return new Promise<T>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Envio cancelado.', 'AbortError'))
      return
    }
    const xhr = new XMLHttpRequest()
    xhr.open(method, buildUrl(path))
    xhr.setRequestHeader('Accept', 'application/json')

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return
      onProgress({ loaded: event.loaded, total: event.total, fraction: event.total ? event.loaded / event.total : 0 })
    }
    xhr.onload = () => {
      const payload = parseBody(xhr.responseText)
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.({ loaded: file.size, total: file.size, fraction: 1 })
        resolve(payload as T)
      } else {
        reject(apiErrorFromResponse(xhr.status, payload))
      }
    }
    xhr.onerror = () => reject(new ApiError(0, NETWORK_ERROR_MESSAGE))
    xhr.onabort = () => reject(new DOMException('Envio cancelado.', 'AbortError'))
    signal?.addEventListener('abort', () => xhr.abort(), { once: true })

    const form = new FormData()
    for (const [key, value] of Object.entries(fields ?? {})) form.append(key, value)
    const name = fileName ?? (file instanceof File ? file.name : 'arquivo')
    form.append(fieldName, file, name)
    xhr.send(form)
  })
}
