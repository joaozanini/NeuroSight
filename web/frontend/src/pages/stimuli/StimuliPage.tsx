import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { hasPermission, useCurrentUser } from '../../api/auth'
import { KIND_LABELS, stimuliApi, stimuliKeys } from '../../api/stimuli'
import type { StimulusCard, StimulusFilters, StimulusKind, StimulusPage } from '../../api/stimuli'
import Badge from '../../components/Badge/Badge'
import Button from '../../components/Button/Button'
import Checkbox from '../../components/Checkbox/Checkbox'
import FormAlert from '../../components/FormAlert/FormAlert'
import PageHeader from '../../components/PageHeader/PageHeader'
import SearchInput from '../../components/SearchInput/SearchInput'
import Segmented from '../../components/Segmented/Segmented'
import Select from '../../components/Select/Select'
import Spinner from '../../components/Spinner/Spinner'
import StimulusThumbnail from '../../components/StimulusThumbnail/StimulusThumbnail'
import Tag from '../../components/Tag/Tag'
import { plural, sentence } from '../../lib/format'
import { useDebouncedValue } from '../../lib/useDebouncedValue'
import { useUrlFilters } from '../../lib/useUrlFilters'
import { usePageTitle } from '../../lib/usePageTitle'
import UploadStimuliModal from './UploadStimuliModal'
import styles from './StimuliPage.module.css'

type KindFilter = 'all' | StimulusKind

const KIND_OPTIONS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'image', label: 'Imagens' },
  { value: 'video', label: 'Vídeos' },
]

// Na URL o tipo fica em português (?tipo=imagens), como as outras rotas do site.
const KIND_PARAM: Record<StimulusKind, string> = { image: 'imagens', video: 'videos' }

function kindFromParam(value: string | null): StimulusKind | '' {
  return value === 'imagens' ? 'image' : value === 'videos' ? 'video' : ''
}

// "42 estímulos na biblioteca: 30 imagens e 12 vídeos."
export function librarySummary(counts: StimulusPage['counts'] | undefined): string {
  if (!counts) return ' '
  if (counts.total === 0) return 'A biblioteca ainda está vazia.'
  const parts = []
  if (counts.images) parts.push(plural(counts.images, 'imagem', 'imagens'))
  if (counts.videos) parts.push(plural(counts.videos, 'vídeo', 'vídeos'))
  return `${plural(counts.total, 'estímulo', 'estímulos')} na biblioteca: ${parts.join(' e ')}.`
}

// W09: a biblioteca em cartões, com busca por nome ou etiqueta, tipo, etiqueta e os arquivados.
// Os filtros ficam na URL; a lista continua carregando ao rolar até o fim.
export default function StimuliPage() {
  usePageTitle('Estímulos')
  const me = useCurrentUser()
  const canUpload = hasPermission(me, 'stimuli.edit')
  const [params, updateParams] = useUrlFilters()
  const filters: StimulusFilters = {
    q: params.get('q') ?? '',
    kind: kindFromParam(params.get('tipo')),
    tag: params.get('etiqueta') ?? '',
    include_archived: params.get('arquivados') === '1',
  }
  const [search, setSearch] = useState(filters.q ?? '')
  const debouncedSearch = useDebouncedValue(search)
  // ?enviar=1 abre o envio direto (atalho "Enviar estímulos" do Início).
  const [uploading, setUploading] = useState(() => canUpload && params.get('enviar') === '1')

  useEffect(() => {
    if (params.get('enviar')) updateParams({ enviar: null })
  }, [])

  useEffect(() => {
    if (debouncedSearch.trim() !== (filters.q ?? '')) updateParams({ q: debouncedSearch.trim() })
    // Só reage ao texto digitado.
  }, [debouncedSearch])

  const library = useInfiniteQuery({
    queryKey: stimuliKeys.list(filters),
    queryFn: ({ pageParam, signal }) => stimuliApi.list(filters, pageParam, signal),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
    placeholderData: keepPreviousData,
  })
  const tags = useQuery({
    queryKey: stimuliKeys.tags(Boolean(filters.include_archived)),
    queryFn: ({ signal }) => stimuliApi.tags(Boolean(filters.include_archived), signal),
  })

  const pages = library.data?.pages ?? []
  const items = pages.flatMap((p) => p.items)
  const counts = pages[0]?.counts
  const tagOptions = [{ value: '', label: 'Todas as etiquetas' }, ...(tags.data ?? []).map((t) => ({ value: t, label: t }))]
  // A etiqueta escolhida continua na lista mesmo que tenha saído da biblioteca.
  if (filters.tag && !tagOptions.some((o) => o.value === filters.tag)) tagOptions.push({ value: filters.tag, label: filters.tag })

  const sentinel = useRef<HTMLDivElement>(null)
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = library
  useEffect(() => {
    const target = sentinel.current
    if (!target || !hasNextPage || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && !isFetchingNextPage) fetchNextPage()
    }, { rootMargin: '400px 0px' })
    observer.observe(target)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const filtering = Boolean(filters.q || filters.kind || filters.tag)
  let body
  if (library.isPending) {
    body = (
      <p className={styles.state}>
        <Spinner label="Carregando" /> Carregando…
      </p>
    )
  } else if (library.isError) {
    body = <FormAlert>{sentence(library.error.message)}</FormAlert>
  } else if (items.length === 0) {
    body = (
      <p className={styles.state}>
        {filtering
          ? 'Nenhum estímulo encontrado com esses filtros.'
          : canUpload
            ? 'Nenhum estímulo ainda. Use “Enviar estímulos” para montar a biblioteca.'
            : 'Nenhum estímulo na biblioteca ainda.'}
      </p>
    )
  } else {
    body = (
      <ul className={styles.grid} aria-label="Estímulos">
        {items.map((s) => (
          <li key={s.id}>
            <StimulusCardLink stimulus={s} />
          </li>
        ))}
      </ul>
    )
  }

  return (
    <>
      <PageHeader
        title="Estímulos"
        subtitle={librarySummary(counts)}
        actions={
          canUpload && (
            <Button icon={Upload} onClick={() => setUploading(true)}>
              Enviar estímulos
            </Button>
          )
        }
      />
      <div className={styles.toolbar}>
        <SearchInput
          placeholder="Buscar por nome ou etiqueta"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          fieldClassName={styles.search}
        />
        <Segmented
          ariaLabel="Tipo de estímulo"
          options={KIND_OPTIONS}
          value={filters.kind || 'all'}
          onChange={(kind) => updateParams({ tipo: kind === 'all' ? null : KIND_PARAM[kind] })}
        />
        <Select
          label="Etiqueta"
          hideLabel
          options={tagOptions}
          value={filters.tag}
          onChange={(e) => updateParams({ etiqueta: e.target.value })}
          fieldClassName={styles.tagFilter}
        />
        <Checkbox
          label="Mostrar arquivados"
          checked={Boolean(filters.include_archived)}
          onChange={(e) => updateParams({ arquivados: e.target.checked ? '1' : null })}
          className={styles.archived}
        />
      </div>
      {body}
      <div ref={sentinel} className={styles.more}>
        {hasNextPage && (
          <Button variant="text" onClick={() => fetchNextPage()} loading={isFetchingNextPage}>
            Mostrar mais
          </Button>
        )}
      </div>

      {canUpload && <UploadStimuliModal open={uploading} onClose={() => setUploading(false)} />}
    </>
  )
}

function StimulusCardLink({ stimulus }: { stimulus: StimulusCard }) {
  const archived = stimulus.status === 'archived'
  return (
    <Link to={`/estimulos/${stimulus.id}`} className={styles.card}>
      <StimulusThumbnail
        src={stimulus.thumbnail_url}
        kind={stimulus.kind}
        duration={stimulus.duration_seconds}
        muted={archived}
      />
      <span className={styles.body}>
        <span className={styles.name}>{stimulus.name}</span>
        <span className={styles.kind}>
          {KIND_LABELS[stimulus.kind]}
          {archived && (
            <Badge tone="neutral" size="sm">
              Arquivado
            </Badge>
          )}
        </span>
        {stimulus.tags.length > 0 && (
          <span className={styles.tags}>
            {stimulus.tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </span>
        )}
      </span>
    </Link>
  )
}
