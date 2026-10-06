// "Chrome no Windows" a partir do user-agent guardado na auditoria (W23, "De onde").

const BROWSERS: [RegExp, string][] = [
  // O app do óculos ("NeuroSight/1.0.0 (Quest Pro 01; Quest Pro)"), no fim de sessão pelo B.
  [/^NeuroSight\//, 'App NeuroSight'],
  [/OculusBrowser\//, 'Navegador do Quest'],
  [/Edg(A|iOS)?\//, 'Edge'],
  [/(OPR|Opera)\//, 'Opera'],
  [/SamsungBrowser\//, 'Samsung Internet'],
  [/(Firefox|FxiOS)\//, 'Firefox'],
  [/(Chrome|CriOS)\//, 'Chrome'],
  [/Version\/[\d.]+.*Safari\//, 'Safari'],
]

const SYSTEMS: [RegExp, string][] = [
  [/Quest/, 'Meta Quest'],
  [/Windows/, 'Windows'],
  [/(iPhone|iPad|iPod)/, 'iOS'],
  [/Android/, 'Android'],
  [/CrOS/, 'ChromeOS'],
  [/Mac OS X|Macintosh/, 'macOS'],
  [/Linux/, 'Linux'],
]

function match(ua: string, table: [RegExp, string][]): string | undefined {
  return table.find(([pattern]) => pattern.test(ua))?.[1]
}

export function describeUserAgent(ua: string | null | undefined): string {
  if (!ua) return 'navegador não informado'
  const browser = match(ua, BROWSERS)
  const system = match(ua, SYSTEMS)
  if (browser && system) return `${browser} no ${system}`
  if (browser) return browser
  if (system) return `navegador no ${system}`
  return ua.length > 60 ? `${ua.slice(0, 57)}…` : ua
}
