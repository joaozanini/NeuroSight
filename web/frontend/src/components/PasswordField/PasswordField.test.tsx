import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PasswordField from './PasswordField'

describe('PasswordField', () => {
  it('marca as regras ao vivo enquanto a pessoa digita', async () => {
    const user = userEvent.setup()
    render(<PasswordField label="Nova senha" showRules />)
    const input = screen.getByLabelText('Nova senha')
    expect(screen.getByText('A senha precisa ter:')).toBeInTheDocument()
    expect(screen.getAllByText('(pendente)', { exact: false })).toHaveLength(4)

    await user.type(input, 'Senha123')
    const rule = (text: string) => screen.getByText(text).closest('li')!
    expect(rule('Pelo menos 8 caracteres')).toHaveTextContent('(atendida)')
    expect(rule('Letras maiúsculas e minúsculas')).toHaveTextContent('(atendida)')
    expect(rule('Pelo menos um número')).toHaveTextContent('(atendida)')
    expect(rule('Pelo menos um símbolo, como ! ou #')).toHaveTextContent('(pendente)')

    await user.type(input, '!')
    expect(rule('Pelo menos um símbolo, como ! ou #')).toHaveTextContent('(atendida)')
    expect(input).toHaveAttribute('aria-describedby', expect.stringContaining('-rules'))
  })

  it('mostra e esconde a senha pelo botão de olho', async () => {
    const user = userEvent.setup()
    render(<PasswordField label="Senha" />)
    const input = screen.getByLabelText('Senha')
    expect(input).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Mostrar a senha' }))
    expect(input).toHaveAttribute('type', 'text')
    await user.click(screen.getByRole('button', { name: 'Esconder a senha' }))
    expect(input).toHaveAttribute('type', 'password')
  })

  it('anuncia o erro no campo', () => {
    render(<PasswordField label="Senha" error="Informe a senha." />)
    const input = screen.getByLabelText('Senha')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Informe a senha.')
  })
})
