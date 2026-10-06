import { describe, expect, it } from 'vitest'
import { ageOn, isoToBr, maskDate, parseBrDate, todayIso } from './dates'

describe('datas digitadas', () => {
  it('põe as barras enquanto digita e ignora o que não é número', () => {
    expect(maskDate('1')).toBe('1')
    expect(maskDate('1203')).toBe('12/03')
    expect(maskDate('12031998')).toBe('12/03/1998')
    expect(maskDate('12/03/1998 e mais')).toBe('12/03/1998')
    expect(maskDate('ab12c0')).toBe('12/0')
  })

  it('converte para o formato da API só datas que existem', () => {
    expect(parseBrDate('12/03/1998')).toBe('1998-03-12')
    expect(parseBrDate('29/02/2024')).toBe('2024-02-29')
    expect(parseBrDate('29/02/2026')).toBeNull()
    expect(parseBrDate('31/04/2026')).toBeNull()
    expect(parseBrDate('12/03/98')).toBeNull()
    expect(parseBrDate('')).toBeNull()
    expect(isoToBr('1998-03-12')).toBe('12/03/1998')
    expect(isoToBr(null)).toBe('')
  })

  it('calcula a idade em anos completos', () => {
    const today = new Date(2026, 9, 5)
    expect(ageOn('1998-03-12', today)).toBe(28)
    expect(ageOn('1998-10-05', today)).toBe(28)
    expect(ageOn('1998-10-06', today)).toBe(27)
    expect(todayIso(today)).toBe('2026-10-05')
  })
})
