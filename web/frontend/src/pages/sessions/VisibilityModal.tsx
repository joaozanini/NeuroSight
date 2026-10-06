import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { sessionsApi, sessionsKeys } from '../../api/sessions'
import type { SessionDetail, Visibility } from '../../api/sessions'
import Button from '../../components/Button/Button'
import Checkbox from '../../components/Checkbox/Checkbox'
import FormAlert from '../../components/FormAlert/FormAlert'
import Modal from '../../components/Modal/Modal'
import RadioCard from '../../components/RadioCard/RadioCard'
import RadioCardGroup from '../../components/RadioCard/RadioCardGroup'
import SearchInput from '../../components/SearchInput/SearchInput'
import Spinner from '../../components/Spinner/Spinner'
import { useToast } from '../../components/Toast/toastContext'
import { sentence } from '../../lib/format'
import styles from './VisibilityModal.module.css'

interface VisibilityModalProps {
  session: SessionDetail
  open: boolean
  onClose: () => void
}

function normalize(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('pt-BR')
}

// W18: só o responsável, pesquisadores escolhidos ou todos. A mudança fica na auditoria.
export default function VisibilityModal({ session, open, onClose }: VisibilityModalProps) {
  return open ? <VisibilityForm session={session} onClose={onClose} /> : null
}

function VisibilityForm({ session, onClose }: { session: SessionDetail; onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [visibility, setVisibility] = useState<Visibility>(session.visibility)
  const [chosen, setChosen] = useState<Set<string>>(() => new Set(session.shared_with.map((u) => u.id)))
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const candidates = useQuery({
    queryKey: sessionsKeys.candidates(session.id),
    queryFn: ({ signal }) => sessionsApi.shareCandidates(session.id, signal),
  })
  const owner = session.owner.name
  const term = normalize(search.trim())
  const shown = (candidates.data ?? []).filter((u) => !term || normalize(u.name).includes(term))

  function toggle(id: string, checked: boolean) {
    setError(null)
    setChosen((current) => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  async function save() {
    if (visibility === 'shared' && chosen.size === 0) {
      setError('Escolha pelo menos um pesquisador.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const updated = await sessionsApi.setVisibility(session.id, visibility, visibility === 'shared' ? [...chosen] : [])
      queryClient.setQueryData(sessionsKeys.detail(updated.id), updated)
      queryClient.invalidateQueries({ queryKey: sessionsKeys.lists })
      queryClient.invalidateQueries({ queryKey: ['audit'] })
      toast.success('Visibilidade alterada.')
      onClose()
    } catch (e) {
      setError(e instanceof ApiError ? sentence(e.message) : 'Não foi possível salvar.')
      setSaving(false)
    }
  }

  let people
  if (candidates.isPending) people = <Spinner label="Carregando os pesquisadores" />
  else if (candidates.isError) people = <p className={styles.empty}>{sentence(candidates.error.message)}</p>
  else if (shown.length === 0) people = <p className={styles.empty}>{term ? 'Nenhum pesquisador encontrado.' : 'Nenhum outro pesquisador ativo.'}</p>
  else
    people = (
      <ul className={styles.people}>
        {shown.map((u) => (
          <li key={u.id}>
            <Checkbox label={u.name} checked={chosen.has(u.id)} onChange={(e) => toggle(u.id, e.target.checked)} className={styles.person} />
            <span className={styles.role}>{u.role_label}</span>
          </li>
        ))}
      </ul>
    )

  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title="Visibilidade da sessão"
      subtitle={`${session.title}, paciente ${session.patient.code}`}
      dismissible={!saving}
      footerNote="A mudança fica registrada na auditoria."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button size="sm" onClick={save} loading={saving}>
            Salvar
          </Button>
        </>
      }
    >
      <RadioCardGroup legend="Quem vê a sessão" hideLegend layout="stack">
        <RadioCard
          name="visibilidade"
          value="private"
          checked={visibility === 'private'}
          onChange={() => setVisibility('private')}
          label="Só o responsável"
          description={`Apenas ${owner} vê a sessão e os dados coletados.`}
        />
        <RadioCard
          name="visibilidade"
          value="shared"
          checked={visibility === 'shared'}
          onChange={() => setVisibility('shared')}
          label="Pesquisadores escolhidos"
          description={`${owner} e os pesquisadores marcados abaixo.`}
        />
        <RadioCard
          name="visibilidade"
          value="all"
          checked={visibility === 'all'}
          onChange={() => setVisibility('all')}
          label="Todos os pesquisadores"
          description="Qualquer pesquisador com acesso ao sistema."
        />
      </RadioCardGroup>
      {visibility === 'shared' && (
        <fieldset className={styles.shared}>
          <legend className={styles.sharedTitle}>Pesquisadores com acesso</legend>
          <SearchInput placeholder="Buscar pesquisador" value={search} onChange={(e) => setSearch(e.target.value)} size="sm" />
          {people}
        </fieldset>
      )}
      {error && <FormAlert className={styles.alert}>{error}</FormAlert>}
    </Modal>
  )
}
