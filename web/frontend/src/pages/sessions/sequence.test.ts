import { describe, expect, it } from 'vitest'
import { aboutDuration, kindText, parseSeconds, reviewSummary, screenTimeText, sequenceHeadline } from './sequence'
import type { SequenceEntry } from './sequence'

const image = (seconds: number | null): SequenceEntry => ({ kind: 'image', duration_seconds: seconds, media_duration_seconds: null })
const video = (seconds: number): SequenceEntry => ({ kind: 'video', duration_seconds: null, media_duration_seconds: seconds })

describe('textos da sequência', () => {
  it('lê o tempo digitado em segundos', () => {
    expect(parseSeconds('5')).toBe(5)
    expect(parseSeconds(' 2,5 ')).toBe(2.5)
    expect(parseSeconds('')).toBeNull()
    expect(parseSeconds('0')).toBeUndefined()
    expect(parseSeconds('abc')).toBeUndefined()
    expect(parseSeconds('3601')).toBeUndefined()
  })

  it('resume a duração como nos protótipos', () => {
    const twelve = Array.from({ length: 12 }, () => image(5))
    expect(sequenceHeadline(twelve)).toBe('12 estímulos, cerca de 1 min')
    expect(reviewSummary(twelve)).toBe('12 imagens, cerca de 1 min, com troca automática a cada 5 s')
    expect(sequenceHeadline([])).toBe('Nenhum estímulo')
    expect(sequenceHeadline([image(null)])).toBe('1 estímulo')
    expect(aboutDuration([image(5), image(null)])).toBe('mais de 5 s')
    expect(reviewSummary([image(5), image(8), video(45)])).toBe('2 imagens e 1 vídeo, cerca de 58 s, com troca automática')
    expect(reviewSummary([image(null), video(80)])).toBe('1 imagem e 1 vídeo, mais de 1 min, com troca manual')
    expect(reviewSummary([image(2.5), image(null)])).toBe('2 imagens, mais de 3 s, com troca automática e manual')
    expect(reviewSummary([video(45)])).toBe('1 vídeo, cerca de 45 s')
  })

  it('descreve o tempo de tela e o tipo', () => {
    expect(screenTimeText(image(5))).toBe('5,0 s')
    expect(screenTimeText(image(null))).toBe('Troca manual')
    expect(screenTimeText(video(45))).toBe('Vídeo inteiro (0:45)')
    expect(kindText('video', 45)).toBe('Vídeo, 0:45')
    expect(kindText('image', null)).toBe('Imagem')
  })
})
