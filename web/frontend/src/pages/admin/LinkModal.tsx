import { useRef } from 'react'
import { Copy } from 'lucide-react'
import type { LinkResult } from '../../api/users'
import Button from '../../components/Button/Button'
import Modal from '../../components/Modal/Modal'
import TextField from '../../components/TextField/TextField'
import { useToast } from '../../components/Toast/toastContext'
import { formatDateTime } from '../../lib/format'
import styles from './LinkModal.module.css'

interface LinkModalProps {
  // Convite (usuário novo ou reenvio) ou redefinição de senha.
  kind: 'invite' | 'reset'
  userName: string
  result: LinkResult | null
  onClose: () => void
}

// Quando o e-mail não sai (servidor sem SMTP ou com falha), o admin copia o link e entrega à
// pessoa por outro meio.
export default function LinkModal({ kind, userName, result, onClose }: LinkModalProps) {
  const toast = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const what = kind === 'invite' ? 'o convite' : 'a redefinição de senha'

  async function copy() {
    if (!result?.link) return
    try {
      await navigator.clipboard.writeText(result.link)
      toast.success('Link copiado.')
    } catch {
      inputRef.current?.select()
      toast.info('Selecionamos o link: copie com Ctrl+C.')
    }
  }

  return (
    <Modal
      open={Boolean(result?.link)}
      onClose={onClose}
      size="sm"
      title={kind === 'invite' ? 'Copie o link do convite' : 'Copie o link de redefinição'}
      footerNote="O link só pode ser usado uma vez."
      footer={
        <Button size="sm" onClick={onClose}>
          Fechar
        </Button>
      }
    >
      <p className={styles.text}>
        O e-mail com {what} não foi enviado. Copie o link abaixo e entregue para {userName} por outro meio.
      </p>
      <div className={styles.row}>
        <TextField
          ref={inputRef}
          label="Link"
          hideLabel
          size="sm"
          value={result?.link ?? ''}
          readOnly
          onFocus={(e) => e.currentTarget.select()}
          fieldClassName={styles.field}
        />
        <Button variant="secondary" size="sm" icon={Copy} onClick={copy}>
          Copiar link
        </Button>
      </div>
      {result && <p className={styles.hint}>Vale até {formatDateTime(result.expires_at)}.</p>}
    </Modal>
  )
}
