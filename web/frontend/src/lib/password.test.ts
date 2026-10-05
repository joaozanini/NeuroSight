import { describe, expect, it } from 'vitest'
import { checkPassword, isStrongPassword } from './password'

describe('regras de senha', () => {
  it('marca cada regra separadamente', () => {
    expect(checkPassword('')).toEqual({ length: false, case: false, number: false, symbol: false })
    expect(checkPassword('Senha123')).toEqual({ length: true, case: true, number: true, symbol: false })
    expect(checkPassword('senha!')).toEqual({ length: false, case: false, number: false, symbol: true })
  })

  it('aceita letras acentuadas como maiúsculas e minúsculas', () => {
    expect(checkPassword('ÁGUAágua').case).toBe(true)
  })

  it('só é forte com as quatro regras', () => {
    expect(isStrongPassword('Senha123')).toBe(false)
    expect(isStrongPassword('Senha123!')).toBe(true)
    expect(isStrongPassword('Sa1!')).toBe(false)
  })
})
