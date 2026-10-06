import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../../App'
import type { StimulusCard, StimulusDetail, StimulusDraft } from '../../api/stimuli'
import { mockApi, reply } from '../../test/api'
import { ADMIN, RESEARCHER } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { FakeXhr } from '../../test/xhr'
import { librarySummary } from './StimuliPage'

beforeEach(() => {
  FakeXhr.reset()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function card(id: string, name: string, extra: Partial<StimulusCard> = {}): StimulusCard {
  return {
    id,
    name,
    kind: 'image',
    status: 'active',
    tags: [],
    duration_seconds: null,
    thumbnail_url: `/api/v1/stimuli/${id}/thumbnail`,
    ...extra,
  }
}

const CARDS = [
  card('s1', 'Montanhas ao amanhecer', { tags: ['paisagem', 'natureza'] }),
  card('s3', 'Ondas na praia', { kind: 'video', duration_seconds: 45, tags: ['paisagem', 'mar'] }),
  card('s9', 'Rosto antigo', { status: 'archived', tags: ['rosto'] }),
]

const PAGE = { items: CARDS.slice(0, 2), total: 2, page: 1, page_size: 48, counts: { total: 42, images: 30, videos: 12 } }

const MONTANHAS: StimulusDetail = {
  id: 's1',
  name: 'Montanhas ao amanhecer',
  description: 'Cordilheira com o sol nascendo atrás das montanhas.',
  kind: 'image',
  format: 'jpg',
  status: 'active',
  original_filename: 'montanhas.jpg',
  size_bytes: 2_936_013,
  width: 3840,
  height: 2160,
  duration_seconds: null,
  has_audio: null,
  tags: ['paisagem', 'natureza'],
  created_at: '2026-09-10T15:00:00Z',
  created_by_name: 'Ana Souza',
  thumbnail_url: '/api/v1/stimuli/s1/thumbnail',
  file_url: '/api/v1/stimuli/s1/file',
  device_status: 'ready',
  device_error: null,
  sessions_count: 0,
  sessions: [],
  can_delete: true,
}

function draft(id: string, file: string, kind: StimulusDraft['kind'] = 'image'): StimulusDraft {
  return {
    id,
    original_filename: file,
    suggested_name: file,
    kind,
    format: kind === 'video' ? 'mp4' : 'jpg',
    size_bytes: 1000,
    width: 640,
    height: 400,
    duration_seconds: kind === 'video' ? 12 : null,
    thumbnail_url: `/api/v1/stimuli/${id}/thumbnail`,
  }
}

describe('W09 Biblioteca de estímulos', () => {
  it('mostra os cartões com tipo, etiquetas e a duração dos vídeos', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /stimuli': PAGE, 'GET /stimuli/tags': ['mar', 'natureza', 'paisagem'] })
    renderWithProviders(<App />, { route: '/estimulos' })
    expect(await screen.findByText('42 estímulos na biblioteca: 30 imagens e 12 vídeos.')).toBeInTheDocument()
    const cards = within(screen.getByRole('list', { name: 'Estímulos' })).getAllByRole('link')
    expect(cards[0]).toHaveAttribute('href', '/estimulos/s1')
    expect(cards[0]).toHaveTextContent('Montanhas ao amanhecer')
    expect(cards[0]).toHaveTextContent('Imagem')
    expect(cards[0]).toHaveTextContent('paisagemnatureza')
    expect(cards[1]).toHaveTextContent('Vídeo')
    expect(cards[1]).toHaveTextContent('Duração 0:45')
    expect(screen.getByRole('button', { name: 'Enviar estímulos' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Todas as etiquetas' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'paisagem' })).toBeInTheDocument()
  })

  it('filtra por tipo, etiqueta, busca e arquivados', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /stimuli': ({ query }) => (query.get('include_archived') === 'true' ? { ...PAGE, items: CARDS, total: 3 } : PAGE),
      'GET /stimuli/tags': ['mar', 'natureza', 'paisagem'],
    })
    renderWithProviders(<App />, { route: '/estimulos' })
    const last = () => api.callsTo('GET', '/stimuli').at(-1)!.query

    await user.click(await screen.findByRole('radio', { name: 'Vídeos' }))
    await waitFor(() => expect(last().get('kind')).toBe('video'))
    await user.selectOptions(screen.getByLabelText('Etiqueta'), 'paisagem')
    await waitFor(() => expect(last().get('tag')).toBe('paisagem'))
    expect(last().get('kind')).toBe('video')
    await user.type(screen.getByRole('searchbox', { name: 'Buscar por nome ou etiqueta' }), 'ondas')
    await waitFor(() => expect(last().get('q')).toBe('ondas'))
    await user.click(screen.getByRole('checkbox', { name: 'Mostrar arquivados' }))
    await waitFor(() => expect(last().get('include_archived')).toBe('true'))
    await waitFor(() => expect(api.callsTo('GET', '/stimuli/tags').at(-1)!.query.get('include_archived')).toBe('true'))
    const archived = await screen.findByRole('link', { name: /Rosto antigo/ })
    expect(archived).toHaveTextContent('Arquivado')
    await user.click(screen.getByRole('radio', { name: 'Todos' }))
    await waitFor(() => expect(last().get('kind')).toBeNull())
    expect(last().get('tag')).toBe('paisagem')
  })

  it('sem permissão de envio, não mostra "Enviar estímulos"', async () => {
    mockApi({ 'GET /me': { ...RESEARCHER, permissions: ['patients.view'] }, 'GET /stimuli': PAGE, 'GET /stimuli/tags': [] })
    renderWithProviders(<App />, { route: '/estimulos?enviar=1' })
    await screen.findByText('Montanhas ao amanhecer')
    expect(screen.queryByRole('button', { name: 'Enviar estímulos' })).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('resume a biblioteca no subtítulo', () => {
    expect(librarySummary({ total: 0, images: 0, videos: 0 })).toBe('A biblioteca ainda está vazia.')
    expect(librarySummary({ total: 1, images: 1, videos: 0 })).toBe('1 estímulo na biblioteca: 1 imagem.')
    expect(librarySummary({ total: 13, images: 1, videos: 12 })).toBe('13 estímulos na biblioteca: 1 imagem e 12 vídeos.')
  })
})

describe('W10 Envio de estímulos', () => {
  function setup() {
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    // Arrastar e soltar não respeita o accept do campo: o .mov chega na lista.
    const user = userEvent.setup({ applyAccept: false })
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /stimuli': PAGE,
      'GET /stimuli/tags': [],
      'POST /stimuli': ({ body }) => (body as { items: { id: string; name: string }[] }).items.map((i) => card(i.id, i.name)),
      'DELETE /stimuli/uploads/:id': undefined,
    })
    renderWithProviders(<App />, { route: '/estimulos?enviar=1' })
    return { user, api }
  }

  const files = () => [
    new File(['a'.repeat(2048)], 'cachoeira-na-mata.jpg', { type: 'image/jpeg' }),
    new File(['b'.repeat(4096)], 'trilha-no-bosque.mp4', { type: 'video/mp4' }),
    new File(['c'], 'video-bruto.mov', { type: 'video/quicktime' }),
  ]

  it('sobe cada arquivo na hora, recusa o formato errado e salva tudo de uma vez', async () => {
    const { user, api } = setup()
    const dialog = await screen.findByRole('dialog', { name: 'Enviar estímulos' })
    expect(within(dialog).getByText('Formatos aceitos: JPG, PNG e MP4.')).toBeInTheDocument()
    await user.upload(dialog.querySelector('input[type="file"]') as HTMLInputElement, files())

    expect(within(dialog).getByRole('heading', { name: 'Arquivos (3)' })).toBeInTheDocument()
    expect(within(dialog).getByText('Formato não aceito. Envie o vídeo em MP4.')).toBeInTheDocument()
    expect(within(dialog).getByText('O arquivo com erro não será enviado.')).toBeInTheDocument()
    expect(FakeXhr.all).toHaveLength(2)

    // O primeiro arquivo fica selecionado, com o nome sugerido.
    expect(within(dialog).getByRole('heading', { name: 'Informações do estímulo' })).toBeInTheDocument()
    expect(within(dialog).getByLabelText('Nome')).toHaveValue('Cachoeira na mata')
    FakeXhr.of('cachoeira-na-mata.jpg').progress(1024, 2048)
    expect(await within(dialog).findByText('Enviando, 50% de 2,0 KB')).toBeInTheDocument()
    FakeXhr.of('cachoeira-na-mata.jpg').respond(201, draft('d1', 'cachoeira-na-mata.jpg'))
    expect(await within(dialog).findByText('Enviado, 2,0 KB')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Descrição'), 'Queda d’água.')
    await user.type(within(dialog).getByLabelText('Etiquetas'), 'Paisagem{Enter}natureza{Enter}')
    await user.click(within(dialog).getByRole('button', { name: /trilha-no-bosque\.mp4/ }))
    expect(within(dialog).getByLabelText('Nome')).toHaveValue('Trilha no bosque')

    // Salvar espera o vídeo terminar de subir.
    await user.click(within(dialog).getByRole('button', { name: 'Salvar na biblioteca' }))
    expect(api.callsTo('POST', '/stimuli')).toHaveLength(0)
    FakeXhr.of('trilha-no-bosque.mp4').respond(201, draft('d2', 'trilha-no-bosque.mp4', 'video'))
    expect(await screen.findByText('2 estímulos salvos na biblioteca.')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(api.callsTo('POST', '/stimuli')[0].body).toEqual({
      items: [
        { id: 'd1', name: 'Cachoeira na mata', description: 'Queda d’água.', tags: ['paisagem', 'natureza'] },
        { id: 'd2', name: 'Trilha no bosque', description: null, tags: [] },
      ],
    })
    expect(FakeXhr.of('cachoeira-na-mata.jpg').url).toBe('/api/v1/stimuli/uploads')
  })

  it('exige o nome e mostra o erro que o servidor devolve', async () => {
    const { user } = setup()
    const dialog = await screen.findByRole('dialog', { name: 'Enviar estímulos' })
    await user.upload(dialog.querySelector('input[type="file"]') as HTMLInputElement, files().slice(0, 2))
    FakeXhr.of('trilha-no-bosque.mp4').respond(415, { detail: 'formato não aceito. Envie o vídeo em MP4' })
    expect(await within(dialog).findByText('Formato não aceito. Envie o vídeo em MP4.')).toBeInTheDocument()
    FakeXhr.of('cachoeira-na-mata.jpg').respond(201, draft('d1', 'cachoeira-na-mata.jpg'))
    await user.clear(within(dialog).getByLabelText('Nome'))
    await user.click(within(dialog).getByRole('button', { name: 'Salvar na biblioteca' }))
    expect(within(dialog).getByText('Informe o nome do estímulo.')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Remover trilha-no-bosque.mp4' }))
    expect(within(dialog).getByRole('heading', { name: 'Arquivos (1)' })).toBeInTheDocument()
  })

  it('Cancelar interrompe os envios e descarta os rascunhos', async () => {
    const { user, api } = setup()
    const dialog = await screen.findByRole('dialog', { name: 'Enviar estímulos' })
    await user.upload(dialog.querySelector('input[type="file"]') as HTMLInputElement, files().slice(0, 2))
    FakeXhr.of('cachoeira-na-mata.jpg').respond(201, draft('d1', 'cachoeira-na-mata.jpg'))
    await within(dialog).findByText('Enviado, 2,0 KB')
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(FakeXhr.of('trilha-no-bosque.mp4').aborted).toBe(true)
    await waitFor(() => expect(api.callsTo('DELETE', '/stimuli/uploads/d1')).toHaveLength(1))
  })
})

describe('W11 Detalhes do estímulo', () => {
  it('mostra a ficha do arquivo e salva nome, descrição e etiquetas', async () => {
    const user = userEvent.setup()
    const api = mockApi({
      'GET /me': RESEARCHER,
      'GET /stimuli/:id': MONTANHAS,
      'PATCH /stimuli/:id': ({ body }) => ({ ...MONTANHAS, ...(body as object) }),
    })
    renderWithProviders(<App />, { route: '/estimulos/s1' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Montanhas ao amanhecer' })).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Estímulos' })).toHaveAttribute('href', '/estimulos')
    expect(screen.getByRole('img', { name: 'Prévia de Montanhas ao amanhecer' })).toHaveAttribute('src', '/api/v1/stimuli/s1/file')
    const main = within(screen.getByRole('main'))
    for (const text of ['Imagem', 'JPG', '3840 × 2160', '2,8 MB', 'Ana Souza', '10/09/2026']) {
      expect(main.getByText(text)).toBeInTheDocument()
    }
    expect(screen.getByRole('heading', { name: 'Uso em sessões' })).toBeInTheDocument()
    expect(screen.getByText('Este estímulo ainda não foi usado em nenhuma sessão.')).toBeInTheDocument()
    // O pesquisador não arquiva nem exclui (W21).
    expect(screen.queryByRole('button', { name: 'Arquivar estímulo' })).not.toBeInTheDocument()

    expect(screen.getByLabelText('Descrição')).toHaveValue('Cordilheira com o sol nascendo atrás das montanhas.')
    await user.click(screen.getByRole('button', { name: 'Remover a etiqueta natureza' }))
    await user.type(screen.getByLabelText('Etiquetas'), 'Montanha{Enter}')
    await user.clear(screen.getByLabelText('Nome'))
    await user.type(screen.getByLabelText('Nome'), 'Montanhas')
    await user.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByText('Alterações salvas.')).toBeInTheDocument()
    expect(api.callsTo('PATCH', '/stimuli/s1')[0].body).toEqual({
      name: 'Montanhas',
      description: 'Cordilheira com o sol nascendo atrás das montanhas.',
      tags: ['paisagem', 'montanha'],
    })
  })

  it('o admin arquiva, desarquiva e exclui o que nunca foi usado', async () => {
    const user = userEvent.setup()
    let status: StimulusDetail['status'] = 'active'
    const api = mockApi({
      'GET /me': ADMIN,
      // Antes de /stimuli/:id, como no servidor.
      'GET /stimuli/tags': [],
      'GET /stimuli/:id': () => ({ ...MONTANHAS, status }),
      'PUT /stimuli/:id/status': ({ body }) => {
        status = (body as { status: StimulusDetail['status'] }).status
        return { ...MONTANHAS, status }
      },
      'DELETE /stimuli/:id': undefined,
      'GET /stimuli': PAGE,
    })
    renderWithProviders(<App />, { route: '/estimulos/s1' })
    expect(await screen.findByRole('heading', { name: 'Arquivar ou excluir estímulo' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Arquivar estímulo' }))
    expect(await screen.findByText('Estímulo arquivado. Ele saiu da biblioteca.')).toBeInTheDocument()
    expect(api.callsTo('PUT', '/stimuli/s1/status')[0].body).toEqual({ status: 'archived' })
    expect(screen.getByRole('heading', { name: 'Estímulo arquivado' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Desarquivar estímulo' }))
    expect(await screen.findByText('Estímulo de volta à biblioteca.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Excluir estímulo' }))
    const confirm = screen.getByRole('dialog', { name: 'Excluir estímulo?' })
    await user.click(within(confirm).getByRole('button', { name: 'Excluir estímulo' }))
    expect(await screen.findByText('Estímulo excluído.')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 1, name: 'Estímulos' })).toBeInTheDocument()
    expect(api.callsTo('DELETE', '/stimuli/s1')).toHaveLength(1)
  })

  it('o que já foi usado só pode ser arquivado e lista as sessões', async () => {
    mockApi({
      'GET /me': ADMIN,
      'GET /stimuli/:id': {
        ...MONTANHAS,
        sessions_count: 2,
        can_delete: false,
        sessions: [
          { id: 'x1', title: 'Paisagens naturais', patient_code: 'P-009', date: '2026-09-29T14:00:00Z' },
          { id: 'x2', title: 'Paisagens naturais', patient_code: 'P-008', date: '2026-09-15T14:00:00Z' },
        ],
      },
    })
    renderWithProviders(<App />, { route: '/estimulos/s1' })
    expect(await screen.findByRole('heading', { name: 'Usado em 2 sessões' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Paisagens naturais' })[0]).toHaveAttribute('href', '/sessoes/x1')
    expect(screen.getByText('Paciente P-009, 29/09/2026')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Arquivar estímulo' })).toBeInTheDocument()
    expect(screen.getByText(/Como já foi usado em sessões, este estímulo não pode ser excluído/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Excluir estímulo' })).not.toBeInTheDocument()
  })

  it('sem permissão de edição os campos ficam só para leitura', async () => {
    mockApi({ 'GET /me': { ...RESEARCHER, permissions: ['patients.view'] }, 'GET /stimuli/:id': MONTANHAS })
    renderWithProviders(<App />, { route: '/estimulos/s1' })
    expect(await screen.findByLabelText('Nome')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Salvar alterações' })).not.toBeInTheDocument()
  })

  it('estímulo inexistente mostra o erro', async () => {
    mockApi({ 'GET /me': RESEARCHER, 'GET /stimuli/:id': reply(404, { detail: 'estímulo não encontrado' }) })
    renderWithProviders(<App />, { route: '/estimulos/zz' })
    expect(await screen.findByText('Estímulo não encontrado.')).toBeInTheDocument()
  })
})
