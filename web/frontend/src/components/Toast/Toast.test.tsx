import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import ToastProvider from './ToastProvider'
import { useToast } from './toastContext'

function Trigger() {
  const toast = useToast()
  return (
    <>
      <button onClick={() => toast.success('Paciente cadastrado.')}>ok</button>
      <button onClick={() => toast.error('Não foi possível salvar.')}>erro</button>
    </>
  )
}

describe('avisos (toast)', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('mostra sucesso como status e erro como alerta, e some sozinho', () => {
    vi.useFakeTimers()
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    act(() => screen.getByText('ok').click())
    act(() => screen.getByText('erro').click())
    expect(screen.getByRole('status')).toHaveTextContent('Paciente cadastrado.')
    expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível salvar.')
    act(() => vi.advanceTimersByTime(5000))
    expect(screen.queryByText('Paciente cadastrado.')).not.toBeInTheDocument()
    expect(screen.getByText('Não foi possível salvar.')).toBeInTheDocument()
    act(() => screen.getByRole('button', { name: 'Fechar aviso' }).click())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('exige o provider', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    expect(() => render(<Trigger />)).toThrow('useToast precisa estar dentro de <ToastProvider>')
  })
})
