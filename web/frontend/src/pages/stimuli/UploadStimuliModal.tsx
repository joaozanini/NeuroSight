import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { STIMULUS_ACCEPT, stimuliApi, stimuliKeys } from '../../api/stimuli'
import type { StimulusDraft } from '../../api/stimuli'
import Button from '../../components/Button/Button'
import Dropzone from '../../components/Dropzone/Dropzone'
import UploadItem from '../../components/Dropzone/UploadItem'
import type { UploadStatus } from '../../components/Dropzone/UploadItem'
import { matchesAccept } from '../../components/Dropzone/accept'
import FormAlert from '../../components/FormAlert/FormAlert'
import Modal from '../../components/Modal/Modal'
import TagInput from '../../components/TagInput/TagInput'
import TextField from '../../components/TextField/TextField'
import Textarea from '../../components/Textarea/Textarea'
import { useToast } from '../../components/Toast/toastContext'
import { sentence } from '../../lib/format'
import { captureVideoFrame, formatProblem, isVideo, objectUrl, revokeUrl, suggestedName } from './uploadHelpers'
import styles from './UploadStimuliModal.module.css'

interface Entry {
  key: number
  file: File
  status: UploadStatus
  progress: number
  error?: string
  draft?: StimulusDraft
  // Miniatura local (imagem escolhida ou quadro do vídeo) até a do servidor chegar.
  preview?: string
  name: string
  nameError?: string
  description: string
  tags: string[]
}

const normalizeTag = (text: string) => text.trim().replace(/\s+/g, ' ').toLocaleLowerCase('pt-BR')

function errorNote(count: number): string | undefined {
  if (count === 0) return undefined
  return count === 1 ? 'O arquivo com erro não será enviado.' : `Os ${count} arquivos com erro não serão enviados.`
}

interface UploadStimuliModalProps {
  open: boolean
  onClose: () => void
}

// W10: cada arquivo sobe na hora, com progresso; o formato errado fica na lista com "Remover".
// Nome, descrição e etiquetas de cada um são editados ao lado. "Salvar na biblioteca" espera os
// envios em andamento e salva todos de uma vez; Cancelar (ou fechar) descarta os rascunhos.
export default function UploadStimuliModal({ open, onClose }: UploadStimuliModalProps) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [entries, setEntries] = useState<Entry[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [saveRequested, setSaveRequested] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const nextKey = useRef(1)
  const controllers = useRef(new Map<number, AbortController>())
  const entriesRef = useRef(entries)
  entriesRef.current = entries

  function update(key: number, changes: Partial<Entry>) {
    setEntries((list) => list.map((e) => (e.key === key ? { ...e, ...changes } : e)))
  }

  function start(entry: Entry) {
    const controller = new AbortController()
    controllers.current.set(entry.key, controller)
    if (isVideo(entry.file)) {
      captureVideoFrame(entry.file).then((preview) => {
        if (preview) update(entry.key, { preview })
      })
    }
    stimuliApi
      .upload(entry.file, { signal: controller.signal, onProgress: (p) => update(entry.key, { progress: p.fraction }) })
      .then((draft) => update(entry.key, { status: 'done', progress: 1, draft }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        update(entry.key, {
          status: 'error',
          error: error instanceof ApiError ? sentence(error.message) : 'Não foi possível enviar o arquivo.',
        })
      })
      .finally(() => controllers.current.delete(entry.key))
  }

  function addFiles(files: File[]) {
    const added = files.map((file): Entry => {
      const key = nextKey.current++
      const base = { key, file, progress: 0, name: suggestedName(file.name), description: '', tags: [] }
      if (!matchesAccept(file, STIMULUS_ACCEPT)) return { ...base, status: 'error', error: formatProblem(file) }
      return { ...base, status: 'uploading', preview: isVideo(file) ? undefined : objectUrl(file) }
    })
    setEntries((list) => [...list, ...added])
    setSelected((current) => current ?? added.find((e) => e.status !== 'error')?.key ?? null)
    for (const entry of added) if (entry.status === 'uploading') start(entry)
  }

  function remove(entry: Entry) {
    controllers.current.get(entry.key)?.abort()
    if (entry.draft) stimuliApi.discard(entry.draft.id).catch(() => undefined)
    revokeUrl(entry.preview)
    setEntries((list) => list.filter((e) => e.key !== entry.key))
  }

  function reset() {
    for (const e of entriesRef.current) revokeUrl(e.preview)
    setEntries([])
    setSelected(null)
    setSaveRequested(false)
    setSaving(false)
    setSaveError(null)
  }

  function cancel() {
    for (const controller of controllers.current.values()) controller.abort()
    controllers.current.clear()
    for (const e of entriesRef.current) if (e.draft) stimuliApi.discard(e.draft.id).catch(() => undefined)
    reset()
    onClose()
  }

  // Sair da página no meio do envio também descarta o que já subiu.
  useEffect(
    () => () => {
      for (const controller of controllers.current.values()) controller.abort()
      for (const e of entriesRef.current) {
        if (e.draft) stimuliApi.discard(e.draft.id).catch(() => undefined)
        revokeUrl(e.preview)
      }
    },
    [],
  )

  const valid = entries.filter((e) => e.status !== 'error')
  const pending = entries.some((e) => e.status === 'uploading')
  const errors = entries.length - valid.length
  const current = valid.find((e) => e.key === selected) ?? valid[0]

  function requestSave() {
    const unnamed = valid.find((e) => !e.name.trim())
    if (unnamed) {
      update(unnamed.key, { nameError: 'Informe o nome do estímulo.' })
      setSelected(unnamed.key)
      return
    }
    setSaveError(null)
    setSaveRequested(true)
  }

  useEffect(() => {
    if (!saveRequested || pending || saving) return
    const ready = entries.filter((e) => e.status === 'done' && e.draft)
    if (ready.length === 0) {
      setSaveRequested(false)
      return
    }
    setSaving(true)
    stimuliApi
      .save(ready.map((e) => ({ id: e.draft!.id, name: e.name.trim(), description: e.description.trim() || null, tags: e.tags })))
      .then((saved) => {
        queryClient.invalidateQueries({ queryKey: stimuliKeys.all })
        queryClient.invalidateQueries({ queryKey: ['audit'] })
        toast.success(saved.length === 1 ? 'Estímulo salvo na biblioteca.' : `${saved.length} estímulos salvos na biblioteca.`)
        reset()
        onClose()
      })
      .catch((error: unknown) => {
        setSaveError(error instanceof ApiError ? sentence(error.message) : 'Não foi possível salvar na biblioteca.')
        setSaveRequested(false)
        setSaving(false)
      })
  }, [saveRequested, pending, saving, entries])

  const busy = saveRequested || saving
  return (
    <Modal
      open={open}
      onClose={cancel}
      title="Enviar estímulos"
      size="lg"
      dismissible={!saving}
      footerNote={errorNote(errors)}
      footer={
        <>
          <Button variant="secondary" onClick={cancel} disabled={saving}>
            Cancelar
          </Button>
          <Button onClick={requestSave} loading={busy} disabled={valid.length === 0}>
            Salvar na biblioteca
          </Button>
        </>
      }
    >
      {saveError && <FormAlert className={styles.alert}>{saveError}</FormAlert>}
      <Dropzone
        onFiles={addFiles}
        accept={STIMULUS_ACCEPT}
        title="Arraste imagens e vídeos para cá"
        description="Formatos aceitos: JPG, PNG e MP4."
        disabled={busy}
      />
      {entries.length > 0 && (
        <div className={styles.columns}>
          <section className={styles.files} aria-labelledby="arquivos">
            <h3 id="arquivos" className={styles.filesTitle}>
              Arquivos ({entries.length})
            </h3>
            <ul className={styles.list}>
              {entries.map((e) => (
                <li key={e.key}>
                  <UploadItem
                    name={e.file.name}
                    size={e.file.size}
                    status={e.status}
                    progress={e.progress}
                    error={e.error}
                    thumbnailUrl={e.preview ?? e.draft?.thumbnail_url}
                    selected={current?.key === e.key}
                    onSelect={e.status === 'error' ? undefined : () => setSelected(e.key)}
                    onRemove={e.status === 'error' ? () => remove(e) : undefined}
                  />
                </li>
              ))}
            </ul>
          </section>
          {current && (
            <section className={styles.info} aria-labelledby="informacoes">
              <h3 id="informacoes" className={styles.infoTitle}>
                Informações do estímulo
              </h3>
              <p className={styles.fileName}>{current.file.name}</p>
              <div className={styles.fields}>
                <TextField
                  key={`nome-${current.key}`}
                  label="Nome"
                  value={current.name}
                  maxLength={120}
                  error={current.nameError}
                  disabled={busy}
                  onChange={(event) => update(current.key, { name: event.target.value, nameError: undefined })}
                />
                <Textarea
                  key={`descricao-${current.key}`}
                  label="Descrição"
                  placeholder="Opcional"
                  rows={3}
                  maxLength={1000}
                  value={current.description}
                  disabled={busy}
                  onChange={(event) => update(current.key, { description: event.target.value })}
                />
                <TagInput
                  key={`etiquetas-${current.key}`}
                  label="Etiquetas"
                  value={current.tags}
                  normalize={normalizeTag}
                  disabled={busy}
                  onChange={(tags) => update(current.key, { tags })}
                />
              </div>
            </section>
          )}
        </div>
      )}
    </Modal>
  )
}
