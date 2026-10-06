// Apoio ao envio de estímulos (W10): nome sugerido, motivo de recusa e a prévia local do arquivo,
// que aparece na lista antes de o servidor gerar a miniatura.

const VIDEO_EXTENSIONS = ['.mov', '.qt', '.avi', '.mkv', '.webm', '.m4v', '.wmv', '.flv', '.3gp', '.mpg', '.mpeg', '.ts']
const IMAGE_EXTENSIONS = ['.gif', '.webp', '.heic', '.heif', '.bmp', '.tif', '.tiff', '.avif', '.svg']

function extension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.slice(dot).toLowerCase() : ''
}

// "cachoeira-na-mata.jpg" -> "Cachoeira na mata" (o mesmo que o servidor sugere).
export function suggestedName(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  const stem = dot > 0 ? fileName.slice(0, dot) : fileName
  const text = stem.replace(/[-_.]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120)
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Estímulo'
}

// Por que um arquivo fora de JPG, PNG e MP4 não entra, com o formato certo para o que ele parece ser.
export function formatProblem(file: File): string {
  const ext = extension(file.name)
  if (file.type.startsWith('video/') || VIDEO_EXTENSIONS.includes(ext)) return 'Formato não aceito. Envie o vídeo em MP4.'
  if (file.type.startsWith('image/') || IMAGE_EXTENSIONS.includes(ext)) return 'Formato não aceito. Envie a imagem em JPG ou PNG.'
  return 'Formato não aceito. Envie imagens em JPG ou PNG e vídeos em MP4.'
}

export function isVideo(file: File): boolean {
  return extension(file.name) === '.mp4' || file.type === 'video/mp4'
}

// Endereço local de uma imagem escolhida (para a miniatura enquanto ela sobe).
export function objectUrl(file: File): string | undefined {
  return typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : undefined
}

export function revokeUrl(url: string | undefined) {
  if (url?.startsWith('blob:') && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
}

// Um quadro do vídeo (a 10% da duração, até 1 s) como imagem, para a lista do envio. Resolve null
// se o navegador não conseguir tocar o arquivo; o servidor manda a miniatura depois do envio.
export function captureVideoFrame(file: File, width = 240): Promise<string | null> {
  return new Promise((resolve) => {
    const url = objectUrl(file)
    if (!url) {
      resolve(null)
      return
    }
    const video = document.createElement('video')
    let settled = false
    const finish = (result: string | null) => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      video.removeAttribute('src')
      revokeUrl(url)
      resolve(result)
    }
    const timer = window.setTimeout(() => finish(null), 8000)
    video.muted = true
    video.preload = 'auto'
    video.playsInline = true
    video.onloadeddata = () => {
      video.currentTime = Math.min(1, (Number.isFinite(video.duration) ? video.duration : 0) * 0.1)
    }
    video.onseeked = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = Math.max(1, Math.round((width * video.videoHeight) / Math.max(1, video.videoWidth)))
        canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
        finish(canvas.toDataURL('image/jpeg', 0.8))
      } catch {
        finish(null)
      }
    }
    video.onerror = () => finish(null)
    video.src = url
  })
}
