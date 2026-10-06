import { describe, expect, it } from 'vitest'
import { describeUserAgent } from './userAgent'

describe('descrição do navegador', () => {
  it.each([
    ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36', 'Chrome no Windows'],
    ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36 Edg/129.0', 'Edge no Windows'],
    ['Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15', 'Safari no macOS'],
    ['Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0', 'Firefox no Linux'],
    ['Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile Safari/604.1', 'Safari no iOS'],
    ['Mozilla/5.0 (X11; Linux x86_64; Quest Pro) AppleWebKit/537.36 OculusBrowser/35.0 Chrome/126.0 Safari/537.36', 'Navegador do Quest no Meta Quest'],
    // Fim de sessão pelo B: o registro leva o app do óculos.
    ['NeuroSight/1.0.0 (Quest Pro 01; Quest Pro)', 'App NeuroSight no Meta Quest'],
  ])('%s', (ua, expected) => {
    expect(describeUserAgent(ua)).toBe(expected)
  })

  it('cai para o texto cru quando não reconhece', () => {
    expect(describeUserAgent('python-requests/2.32')).toBe('python-requests/2.32')
    expect(describeUserAgent(null)).toBe('navegador não informado')
  })
})
