// Validações dos formulários (zod), com as mensagens em português.
import { z } from 'zod'
import { isStrongPassword } from './password'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const emailField = z
  .string()
  .trim()
  .min(1, 'Informe o e-mail.')
  .refine((value) => EMAIL_PATTERN.test(value), 'Informe um e-mail válido.')

// Senha nova com as regras da W03/W05 (a lista "A senha precisa ter:" mostra o que falta).
export const newPasswordField = z.string().refine(isStrongPassword, 'A senha ainda não atende a todas as regras.')

export const confirmPasswordField = z.string().min(1, 'Repita a senha para confirmar.')

export const PASSWORDS_DIFFER = 'As senhas não conferem.'
