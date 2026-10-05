// Regras de senha da W03 (definir senha) e da W05 (alterar senha), marcadas ao vivo no formulário.
// O backend precisa aplicar exatamente as mesmas regras ao salvar.

export type PasswordRuleId = 'length' | 'case' | 'number' | 'symbol'

export interface PasswordRule {
  id: PasswordRuleId
  label: string
  test: (value: string) => boolean
}

export const PASSWORD_RULES: PasswordRule[] = [
  { id: 'length', label: 'Pelo menos 8 caracteres', test: (v) => [...v].length >= 8 },
  {
    id: 'case',
    label: 'Letras maiúsculas e minúsculas',
    test: (v) => /\p{Lu}/u.test(v) && /\p{Ll}/u.test(v),
  },
  { id: 'number', label: 'Pelo menos um número', test: (v) => /\p{Nd}/u.test(v) },
  { id: 'symbol', label: 'Pelo menos um símbolo, como ! ou #', test: (v) => /[^\p{L}\p{N}\s]/u.test(v) },
]

export function checkPassword(value: string): Record<PasswordRuleId, boolean> {
  return Object.fromEntries(PASSWORD_RULES.map((r) => [r.id, r.test(value)])) as Record<PasswordRuleId, boolean>
}

export function isStrongPassword(value: string): boolean {
  return PASSWORD_RULES.every((r) => r.test(value))
}
