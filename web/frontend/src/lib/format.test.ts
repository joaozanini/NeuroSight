import { describe, expect, it } from 'vitest'
import {
  formatBytes,
  formatClock,
  formatDate,
  formatDateTime,
  formatDecimal,
  formatDuration,
  formatMediaDuration,
  formatNumber,
  formatPercent,
  formatRelative,
  formatSeconds,
  initials,
  plural,
  toDate,
} from './format'

describe('datas e horários', () => {
  it('formata dd/mm/aaaa e hora', () => {
    const d = new Date(2026, 8, 29, 14, 31, 7)
    expect(formatDate(d)).toBe('29/09/2026')
    expect(formatDateTime(d)).toBe('29/09/2026, 14:31')
    expect(formatDateTime(d, true)).toBe('29/09/2026, 14:31:07')
  })

  it('lê data sem hora no fuso local (nascimento não volta um dia)', () => {
    expect(formatDate('1998-03-12')).toBe('12/03/1998')
    expect(toDate('1998-03-12').getHours()).toBe(0)
  })

  it('usa Hoje e Ontem nos horários relativos', () => {
    const now = new Date(2026, 8, 29, 16, 0)
    expect(formatRelative(new Date(2026, 8, 29, 14, 10), now)).toBe('Hoje, 14:10')
    expect(formatRelative(new Date(2026, 8, 28, 17, 30), now)).toBe('Ontem, 17:30')
    expect(formatRelative(new Date(2026, 8, 27, 9, 2), now)).toBe('27/09/2026')
  })
})

describe('números', () => {
  it('usa vírgula decimal e ponto de milhar', () => {
    expect(formatSeconds(5)).toBe('5,0 s')
    expect(formatDecimal(2.84)).toBe('2,8')
    expect(formatNumber(1248)).toBe('1.248')
    expect(formatPercent(0.89)).toBe('89%')
  })

  it('formata tamanhos como nos protótipos', () => {
    expect(formatBytes(2.8 * 1024 * 1024)).toBe('2,8 MB')
    expect(formatBytes(86 * 1024 * 1024)).toBe('86 MB')
    expect(formatBytes(415 * 1024 * 1024)).toBe('415 MB')
    expect(formatBytes(212 * 1024)).toBe('212 KB')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1023.9 * 1024)).toBe('1,0 MB')
  })

  it('formata tempos de sessão e de mídia', () => {
    expect(formatClock(36)).toBe('00:36')
    expect(formatClock(65)).toBe('01:05')
    expect(formatClock(3723)).toBe('1:02:03')
    expect(formatMediaDuration(45)).toBe('0:45')
    expect(formatMediaDuration(80)).toBe('1:20')
    expect(formatDuration(110)).toBe('1 min 50 s')
    expect(formatDuration(45)).toBe('45 s')
    expect(formatDuration(0)).toBe('0 s')
  })

  it('monta plurais e iniciais', () => {
    expect(plural(1, 'sessão', 'sessões')).toBe('1 sessão')
    expect(plural(3, 'sessão', 'sessões')).toBe('3 sessões')
    expect(initials('Ana Souza')).toBe('AS')
    expect(initials('  carlos   de lima ')).toBe('CL')
    expect(initials('Igor')).toBe('I')
  })
})
