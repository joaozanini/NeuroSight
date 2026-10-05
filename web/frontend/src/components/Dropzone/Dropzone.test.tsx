import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Dropzone from './Dropzone'
import FileField from './FileField'
import UploadItem from './UploadItem'
import { matchesAccept } from './accept'

const ACCEPT = '.jpg,.jpeg,.png,.mp4'

describe('matchesAccept', () => {
  it('confere extensão e tipo MIME', () => {
    expect(matchesAccept(new File([''], 'foto.JPG'), ACCEPT)).toBe(true)
    expect(matchesAccept(new File([''], 'video.mp4'), ACCEPT)).toBe(true)
    expect(matchesAccept(new File([''], 'video-bruto.mov'), ACCEPT)).toBe(false)
    expect(matchesAccept(new File([''], 'x', { type: 'video/mp4' }), 'video/*')).toBe(true)
    expect(matchesAccept(new File([''], 'x', { type: 'image/png' }), 'video/*')).toBe(false)
    expect(matchesAccept(new File([''], 'qualquer'), undefined)).toBe(true)
  })
})

describe('Dropzone', () => {
  it('entrega todos os arquivos soltos, inclusive os de formato errado', () => {
    const onFiles = vi.fn()
    render(<Dropzone onFiles={onFiles} accept={ACCEPT} title="Arraste imagens e vídeos para cá" />)
    const files = [new File(['a'], 'cachoeira.jpg'), new File(['b'], 'video-bruto.mov')]
    const zone = screen.getByText('Arraste imagens e vídeos para cá').closest('div')!.parentElement!
    fireEvent.dragEnter(zone, { dataTransfer: { types: ['Files'], files } })
    fireEvent.drop(zone, { dataTransfer: { types: ['Files'], files } })
    expect(onFiles).toHaveBeenCalledWith(files)
  })

  it('abre a escolha de arquivos pelo botão', async () => {
    const user = userEvent.setup()
    const onFiles = vi.fn()
    const { container } = render(<Dropzone onFiles={onFiles} accept={ACCEPT} />)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).toHaveAttribute('accept', ACCEPT)
    const file = new File(['a'], 'rosto.png', { type: 'image/png' })
    await user.upload(input, file)
    expect(onFiles).toHaveBeenCalledWith([file])
    expect(screen.getByRole('button', { name: 'Escolher arquivos' })).toBeInTheDocument()
  })
})

describe('FileField', () => {
  it('mostra o vazio e depois o arquivo anexado com o tamanho', () => {
    const { rerender } = render(<FileField label="Termo" buttonLabel="Anexar PDF" onFile={() => undefined} />)
    expect(screen.getByText('Nenhum arquivo anexado')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Anexar PDF/ })).toBeInTheDocument()
    rerender(<FileField label="Termo" fileName="termo-P-014.pdf" fileSize={212 * 1024} onFile={() => undefined} />)
    expect(screen.getByText('termo-P-014.pdf (212 KB)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Trocar arquivo/ })).toBeInTheDocument()
  })
})

describe('UploadItem', () => {
  it('descreve envio, conclusão e erro como nos protótipos', () => {
    const { rerender } = render(<UploadItem name="trilha-no-bosque.mp4" size={86 * 1024 * 1024} status="uploading" progress={0.64} />)
    expect(screen.getByText('Enviando, 64% de 86 MB')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Envio de trilha-no-bosque.mp4' })).toHaveAttribute('aria-valuenow', '64')
    rerender(<UploadItem name="cachoeira-na-mata.jpg" size={2.4 * 1024 * 1024} status="done" />)
    expect(screen.getByText('Enviado, 2,4 MB')).toBeInTheDocument()
    const onRemove = vi.fn()
    rerender(<UploadItem name="video-bruto.mov" status="error" error="Formato não aceito. Envie o vídeo em MP4." onRemove={onRemove} />)
    expect(screen.getByText('Formato não aceito. Envie o vídeo em MP4.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remover video-bruto.mov' }))
    expect(onRemove).toHaveBeenCalled()
  })
})
