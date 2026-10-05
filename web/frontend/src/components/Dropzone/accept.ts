// Confere um arquivo contra uma lista no formato do atributo `accept` (".jpg,.png,video/mp4").
// Arrastar e soltar não respeita o `accept` do input, então a tela confere cada arquivo.
export function matchesAccept(file: File, accept?: string): boolean {
  if (!accept) return true
  const name = file.name.toLowerCase()
  const type = (file.type || '').toLowerCase()
  return accept
    .split(',')
    .map((token) => token.trim().toLowerCase())
    .filter(Boolean)
    .some((token) => {
      if (token.startsWith('.')) return name.endsWith(token)
      if (token.endsWith('/*')) return type.startsWith(token.slice(0, -1))
      return type === token
    })
}
