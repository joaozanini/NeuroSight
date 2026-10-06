import { useEffect, useRef, useState } from 'react'
import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query'
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core'
import type { Announcements, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, X } from 'lucide-react'
import { stimuliApi, stimuliKeys } from '../../../api/stimuli'
import type { StimulusCard, StimulusFilters, StimulusKind } from '../../../api/stimuli'
import Button from '../../../components/Button/Button'
import Card from '../../../components/Card/Card'
import CheckCircleFilled from '../../../components/icons/CheckCircleFilled'
import SearchInput from '../../../components/SearchInput/SearchInput'
import Segmented from '../../../components/Segmented/Segmented'
import Spinner from '../../../components/Spinner/Spinner'
import StimulusThumbnail from '../../../components/StimulusThumbnail/StimulusThumbnail'
import { cx } from '../../../lib/cx'
import { sentence } from '../../../lib/format'
import { useDebouncedValue } from '../../../lib/useDebouncedValue'
import { kindText, sequenceHeadline } from '../sequence'
import WizardFooter from './WizardFooter'
import { entries, itemSeconds, newItem } from './wizardState'
import type { WizardItem } from './wizardState'
import shared from './Wizard.module.css'
import styles from './StimuliStep.module.css'

type KindFilter = 'all' | StimulusKind

const KIND_OPTIONS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'image', label: 'Imagens' },
  { value: 'video', label: 'Vídeos' },
]

interface StimuliStepProps {
  items: WizardItem[]
  onChange: (items: WizardItem[]) => void
  onBack: () => void
  onContinue: () => void
}

// Etapa 3 da W13: a biblioteca à esquerda (busca, abas, Adicionar) e a sequência arrastável à direita,
// com o tempo de tela de cada imagem.
export default function StimuliStep({ items, onChange, onBack, onContinue }: StimuliStepProps) {
  const [error, setError] = useState<string | null>(null)
  const added = new Set(items.map((i) => i.stimulus_id))
  const invalid = new Set(items.filter((i) => itemSeconds(i) === undefined).map((i) => i.stimulus_id))

  function add(stimulus: StimulusCard) {
    setError(null)
    onChange([...items, newItem(stimulus)])
  }

  function next() {
    if (items.length === 0) {
      setError('Adicione pelo menos um estímulo à sequência.')
      return
    }
    if (invalid.size > 0) {
      setError('Confira os tempos destacados: use de 0,1 a 3.600 segundos, ou deixe em branco para trocar manualmente.')
      return
    }
    onContinue()
  }

  return (
    <>
      <Card padding="none" className={styles.card}>
        <Library added={added} onAdd={add} />
        <Sequence
          items={items}
          invalid={invalid}
          onChange={(next) => {
            setError(null)
            onChange(next)
          }}
        />
      </Card>
      {error && (
        <p className={shared.error} role="alert">
          {error}
        </p>
      )}
      <WizardFooter
        start={
          <Button variant="secondary" onClick={onBack}>
            Voltar
          </Button>
        }
        end={<Button onClick={next}>Continuar</Button>}
      />
    </>
  )
}

function Library({ added, onAdd }: { added: Set<string>; onAdd: (stimulus: StimulusCard) => void }) {
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState<KindFilter>('all')
  const q = useDebouncedValue(search).trim()
  const filters: StimulusFilters = { q, kind: kind === 'all' ? '' : kind }
  const library = useInfiniteQuery({
    queryKey: stimuliKeys.list(filters),
    queryFn: ({ pageParam, signal }) => stimuliApi.list(filters, pageParam, signal),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
    placeholderData: keepPreviousData,
  })
  const stimuli = library.data?.pages.flatMap((p) => p.items) ?? []

  // Busca mais ao chegar perto do fim da lista (que rola dentro do painel).
  const listRef = useRef<HTMLUListElement>(null)
  const sentinel = useRef<HTMLLIElement>(null)
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = library
  useEffect(() => {
    const target = sentinel.current
    if (!target || !hasNextPage || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (found) => {
        if (found.some((e) => e.isIntersecting) && !isFetchingNextPage) fetchNextPage()
      },
      { root: listRef.current, rootMargin: '200px 0px' },
    )
    observer.observe(target)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, stimuli.length])

  let body
  if (library.isPending) {
    body = <Spinner label="Carregando a biblioteca" />
  } else if (library.isError) {
    body = <p className={styles.empty}>{sentence(library.error.message)}</p>
  } else if (stimuli.length === 0) {
    body = <p className={styles.empty}>{q || kind !== 'all' ? 'Nenhum estímulo encontrado.' : 'A biblioteca ainda está vazia.'}</p>
  } else {
    body = (
      <ul ref={listRef} className={styles.library} aria-label="Estímulos da biblioteca">
        {stimuli.map((s) => (
          <li key={s.id} className={styles.libraryItem}>
            <StimulusThumbnail src={s.thumbnail_url} kind={s.kind} className={styles.thumb} />
            <span className={styles.text}>
              <span className={styles.name} title={s.name}>
                {s.name}
              </span>
              <span className={styles.kind}>{kindText(s.kind, s.duration_seconds)}</span>
            </span>
            {added.has(s.id) ? (
              <span className={styles.added}>
                <CheckCircleFilled size={18} />
                Adicionado
              </span>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => onAdd(s)} aria-label={`Adicionar ${s.name}`}>
                Adicionar
              </Button>
            )}
          </li>
        ))}
        <li ref={sentinel} className={styles.more}>
          {hasNextPage && (
            <Button variant="text" onClick={() => fetchNextPage()} loading={isFetchingNextPage}>
              Mostrar mais
            </Button>
          )}
        </li>
      </ul>
    )
  }

  return (
    <section className={styles.libraryPanel} aria-labelledby="biblioteca">
      <h2 id="biblioteca" className={styles.panelTitle}>
        Biblioteca
      </h2>
      <p className={styles.panelLead}>Escolha os estímulos e adicione à sequência.</p>
      <SearchInput placeholder="Buscar por nome" value={search} onChange={(e) => setSearch(e.target.value)} fieldClassName={styles.search} />
      <Segmented options={KIND_OPTIONS} value={kind} onChange={setKind} ariaLabel="Tipo de estímulo" className={styles.kinds} />
      {body}
    </section>
  )
}

interface SequenceProps {
  items: WizardItem[]
  invalid: Set<string>
  onChange: (items: WizardItem[]) => void
}

function Sequence({ items, invalid, onChange }: SequenceProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const nameOf = (id: string | number) => items.find((i) => i.stimulus_id === id)?.name ?? 'O estímulo'
  const positionOf = (id: string | number) => items.findIndex((i) => i.stimulus_id === id) + 1
  const announcements: Announcements = {
    onDragStart: ({ active }) => `${nameOf(active.id)} pego, na posição ${positionOf(active.id)}.`,
    onDragOver: ({ active, over }) => (over ? `${nameOf(active.id)} sobre a posição ${positionOf(over.id)}.` : `${nameOf(active.id)} fora da lista.`),
    onDragEnd: ({ active, over }) => (over ? `${nameOf(active.id)} solto na posição ${positionOf(over.id)}.` : `${nameOf(active.id)} solto.`),
    onDragCancel: ({ active }) => `Movimento de ${nameOf(active.id)} cancelado.`,
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return
    const from = items.findIndex((i) => i.stimulus_id === active.id)
    const to = items.findIndex((i) => i.stimulus_id === over.id)
    onChange(arrayMove(items, from, to))
  }

  function update(id: string, seconds: string) {
    onChange(items.map((i) => (i.stimulus_id === id ? { ...i, seconds } : i)))
  }

  return (
    <section className={styles.sequencePanel} aria-labelledby="sequencia">
      <div className={styles.sequenceHeader}>
        <h2 id="sequencia" className={styles.panelTitle}>
          Sequência da sessão
        </h2>
        <span className={styles.total} aria-live="polite">
          {sequenceHeadline(entries(items))}
        </span>
      </div>
      <p className={styles.panelLead}>
        Arraste para mudar a ordem. O tempo vale só para imagens: em branco, a troca é feita por você durante a sessão.
      </p>
      {items.length === 0 ? (
        <p className={styles.emptySequence}>Nenhum estímulo na sequência. Adicione pela biblioteca ao lado.</p>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={onDragEnd}
          accessibility={{
            announcements,
            screenReaderInstructions: {
              draggable: 'Para mudar a ordem, aperte espaço ou Enter, mova com as setas e aperte espaço de novo para soltar. Esc cancela.',
            },
          }}
        >
          <SortableContext items={items.map((i) => i.stimulus_id)} strategy={verticalListSortingStrategy}>
            <ol className={styles.sequence} aria-label="Sequência da sessão">
              {items.map((item, index) => (
                <SequenceRow
                  key={item.stimulus_id}
                  item={item}
                  position={index + 1}
                  invalid={invalid.has(item.stimulus_id)}
                  onSeconds={(value) => update(item.stimulus_id, value)}
                  onRemove={() => onChange(items.filter((i) => i.stimulus_id !== item.stimulus_id))}
                />
              ))}
            </ol>
          </SortableContext>
        </DndContext>
      )}
    </section>
  )
}

interface SequenceRowProps {
  item: WizardItem
  position: number
  invalid: boolean
  onSeconds: (value: string) => void
  onRemove: () => void
}

function SequenceRow({ item, position, invalid, onSeconds, onRemove }: SequenceRowProps) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: item.stimulus_id,
  })
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      className={cx(styles.row, isDragging && styles.dragging)}
    >
      <button
        type="button"
        ref={setActivatorNodeRef}
        className={styles.handle}
        aria-label={`Mover ${item.name}, posição ${position}`}
        {...attributes}
        {...listeners}
      >
        <GripVertical size={20} aria-hidden />
      </button>
      <span className={styles.position}>{position}</span>
      <StimulusThumbnail src={item.thumbnail_url} kind={item.kind} className={styles.thumb} />
      <span className={styles.text}>
        <span className={styles.name} title={item.name}>
          {item.name}
        </span>
        <span className={styles.kind}>{kindText(item.kind, item.media_duration_seconds)}</span>
      </span>
      {item.kind === 'image' ? (
        <span className={styles.time}>
          <input
            type="text"
            inputMode="decimal"
            value={item.seconds}
            onChange={(e) => onSeconds(e.target.value)}
            aria-label={`Tempo de tela de ${item.name}, em segundos`}
            aria-invalid={invalid || undefined}
            className={styles.seconds}
            maxLength={7}
          />
          <span aria-hidden>s</span>
        </span>
      ) : (
        <span className={styles.time} />
      )}
      <button type="button" className={styles.remove} onClick={onRemove} aria-label={`Remover ${item.name} da sequência`}>
        <X size={20} aria-hidden />
      </button>
    </li>
  )
}
