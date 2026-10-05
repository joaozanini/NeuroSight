import { useState } from 'react'
import type { ReactNode } from 'react'
import { NavigationType, UNSAFE_LocationContext, UNSAFE_RouteContext } from 'react-router-dom'
import { Download, Plus, Upload } from 'lucide-react'
import {
  Avatar,
  Badge,
  Button,
  Card,
  Checkbox,
  DangerZone,
  Dropzone,
  FileField,
  FormAlert,
  LinkButton,
  Modal,
  PageHeader,
  Pagination,
  PasswordField,
  ProgressBar,
  RadioCard,
  RadioCardGroup,
  SearchInput,
  Segmented,
  Select,
  StatCard,
  StatusBadge,
  Stepper,
  Table,
  Tabs,
  Tag,
  TagInput,
  TextField,
  TextLink,
  Textarea,
  UploadItem,
  useToast,
} from '../../components'
import type { Column } from '../../components'
import Sidebar from '../../layouts/Sidebar'
import BrandPanel from '../../layouts/BrandPanel'
import { usePageTitle } from '../../lib/usePageTitle'
import styles from './ComponentsPage.module.css'

// Vitrine dos componentes de base, com os textos dos protótipos. Só existe no `npm run dev`.

interface PatientRow {
  code: string
  name: string
  birth: string
  sessions: number
  last: string
}

const PATIENTS: PatientRow[] = [
  { code: 'P-014', name: 'Mariana Alves', birth: '12/03/1998', sessions: 3, last: '29/09/2026' },
  { code: 'P-009', name: 'Rafael Nunes', birth: '05/11/2001', sessions: 2, last: '29/09/2026' },
  { code: 'P-015', name: 'Beatriz Carvalho', birth: '21/07/1995', sessions: 1, last: '28/09/2026' },
]

const PATIENT_COLUMNS: Column<PatientRow>[] = [
  { key: 'code', header: 'Código', render: (p) => <strong>{p.code}</strong> },
  { key: 'name', header: 'Nome', render: (p) => <TextLink to="#" underline={false}>{p.name}</TextLink> },
  { key: 'birth', header: 'Data de nascimento', render: (p) => p.birth },
  { key: 'sessions', header: 'Sessões', align: 'right', render: (p) => p.sessions },
  { key: 'last', header: 'Última sessão', render: (p) => p.last },
  {
    key: 'actions',
    header: 'Ações',
    align: 'right',
    render: () => (
      <span className={styles.rowActions}>
        <TextLink to="#">Editar</TextLink>
        <TextLink to="#">Nova sessão</TextLink>
      </span>
    ),
  },
]

// Mostra um trecho como se o endereço fosse `path` (para ver o item ativo do menu e das abas).
// Usa os contextos internos do router: serve só para esta vitrine de desenvolvimento.
function AtLocation({ path, children }: { path: string; children: ReactNode }) {
  const location = { pathname: path, search: '', hash: '', state: null, key: 'vitrine' }
  return (
    <UNSAFE_RouteContext.Provider value={{ outlet: null, matches: [], isDataRoute: false }}>
      <UNSAFE_LocationContext.Provider value={{ location, navigationType: NavigationType.Pop }}>
        {children}
      </UNSAFE_LocationContext.Provider>
    </UNSAFE_RouteContext.Provider>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      {children}
    </section>
  )
}

export default function ComponentsPage() {
  usePageTitle('Componentes')
  const toast = useToast()
  const [modalOpen, setModalOpen] = useState(false)
  const [sex, setSex] = useState('F')
  const [role, setRole] = useState('researcher')
  const [kind, setKind] = useState<'all' | 'image' | 'video'>('all')
  const [tab, setTab] = useState('heatmap')
  const [tags, setTags] = useState(['paisagem', 'natureza'])
  const [page, setPage] = useState(1)
  const [dropped, setDropped] = useState<string[]>([])

  return (
    <div className={styles.page}>
      <PageHeader
        title="Componentes"
        subtitle="Vitrine dos componentes de base, com os textos dos protótipos."
        back={{ to: '/', label: 'Início' }}
        badge={<Tag shape="rounded" size="md">dev</Tag>}
        actions={
          <>
            <Button variant="secondary">Novo paciente</Button>
            <LinkButton to="/sessoes/nova" icon={Plus}>
              Nova sessão
            </LinkButton>
          </>
        }
      />

      <Section title="Botões">
        <div className={styles.row}>
          <Button icon={Plus}>Novo paciente</Button>
          <Button variant="secondary">Editar</Button>
          <Button variant="danger" size="sm">Inativar paciente</Button>
          <Button variant="danger-subtle" size="sm">Interromper sessão</Button>
          <Button variant="secondary" icon={Download} size="sm">Exportar CSV</Button>
          <Button loading>Salvando</Button>
        </div>
        <div className={styles.row}>
          <Button disabled>Salvar permissões</Button>
          <Button variant="secondary" size="sm" disabled>Anterior</Button>
          <Button variant="text">Reenviar convite</Button>
          <Button variant="text-danger">Desativar</Button>
          <TextLink to="#">Esqueci minha senha</TextLink>
        </div>
        <div className={styles.narrow}>
          <Button size="lg" block>
            Entrar
          </Button>
        </div>
      </Section>

      <Section title="Campos">
        <div className={styles.grid2}>
          <TextField label="Código do participante" defaultValue="P-016" hint="O código identifica o paciente nas análises e exportações, sem expor o nome." />
          <TextField label="E-mail" placeholder="nome@exemplo.com" error="Informe um e-mail válido." />
          <PasswordField label="Nova senha" showRules defaultValue="Senha123" />
          <div className={styles.stack}>
            <PasswordField label="Senha" />
            <Select
              label="Status"
              hideLabel
              options={[
                { value: '', label: 'Todos os status' },
                { value: 'running', label: 'Em andamento' },
                { value: 'completed', label: 'Concluída' },
              ]}
            />
            <SearchInput placeholder="Buscar por nome ou código" />
            <Checkbox label="Mostrar inativos" />
            <Checkbox label="Gravar a sessão" strong defaultChecked description="A gravação mostra o que o paciente viu no óculos e fica junto com os dados de rastreamento." />
          </div>
          <Textarea label="Observações" placeholder="Opcional" />
          <TagInput label="Etiquetas" value={tags} onChange={setTags} />
        </div>
        <div className={styles.grid2}>
          <RadioCardGroup legend="Sexo">
            {[
              ['F', 'Feminino'],
              ['M', 'Masculino'],
              ['N', 'Prefiro não informar'],
            ].map(([value, label]) => (
              <RadioCard key={value} appearance="control" name="sexo" value={value} label={label} checked={sex === value} onChange={() => setSex(value)} />
            ))}
          </RadioCardGroup>
          <RadioCardGroup legend="Perfil" layout="stack">
            <RadioCard
              name="perfil"
              value="researcher"
              label="Pesquisador"
              description="Cadastra pacientes e estímulos, configura e executa sessões e analisa os dados."
              checked={role === 'researcher'}
              onChange={() => setRole('researcher')}
            />
            <RadioCard
              name="perfil"
              value="admin"
              label="Admin"
              description="Tudo o que o pesquisador faz, mais usuários, permissões, visibilidade das sessões e auditoria."
              checked={role === 'admin'}
              onChange={() => setRole('admin')}
            />
          </RadioCardGroup>
        </div>
        <FileField label="Termo de consentimento (TCLE)" accept=".pdf" buttonLabel="Anexar PDF" onFile={(f) => toast.info(`Arquivo: ${f.name}`)} />
        <FileField accept=".pdf" fileName="termo-P-014.pdf" fileSize={212 * 1024} onFile={() => undefined} />
      </Section>

      <Section title="Abas e seleção">
        <AtLocation path="/admin/usuarios">
          <Tabs
            ariaLabel="Administração"
            items={[
              { label: 'Usuários', to: '/admin/usuarios' },
              { label: 'Perfis e permissões', to: '/admin/permissoes' },
              { label: 'Auditoria', to: '/admin/auditoria' },
            ]}
          />
        </AtLocation>
        <div className={styles.row}>
          <Segmented
            ariaLabel="Tipo de estímulo"
            value={kind}
            onChange={setKind}
            options={[
              { value: 'all', label: 'Todos' },
              { value: 'image', label: 'Imagens' },
              { value: 'video', label: 'Vídeos' },
            ]}
          />
          <Segmented
            ariaLabel="Visualização"
            value={tab}
            onChange={setTab}
            options={[
              { value: 'heatmap', label: 'Mapa de calor' },
              { value: 'path', label: 'Trajetória do olhar' },
            ]}
          />
        </div>
        <Stepper steps={['Paciente', 'Informações', 'Estímulos', 'Revisão']} current={1} />
      </Section>

      <Section title="Tabela e paginação">
        <Table caption="Pacientes" columns={PATIENT_COLUMNS} rows={PATIENTS} rowKey={(p) => p.code} />
        <Pagination page={page} pageSize={8} total={15} onPageChange={setPage} />
        <Pagination
          page={1}
          pageSize={8}
          total={14}
          noun="usuários"
          note="Usuários não são excluídos, só desativados, para manter o histórico da auditoria."
          onPageChange={() => undefined}
        />
      </Section>

      <Section title="Selos, etiquetas e avatar">
        <div className={styles.row}>
          <StatusBadge kind="session" status="running" />
          <StatusBadge kind="session" status="awaiting_data" />
          <StatusBadge kind="session" status="configured" />
          <StatusBadge kind="session" status="interrupted" />
          <StatusBadge kind="session" status="completed" />
        </div>
        <div className={styles.row}>
          <StatusBadge kind="user" status="active" />
          <StatusBadge kind="user" status="invited" />
          <StatusBadge kind="user" status="inactive" />
          <Badge tone="info" size="sm">Você</Badge>
          <Tag>paisagem</Tag>
          <Tag>natureza</Tag>
          <Tag shape="rounded" size="md">P-014</Tag>
          <Tag size="md">Pesquisador</Tag>
          <Avatar name="Ana Souza" />
          <Avatar name="Carlos Lima" />
        </div>
      </Section>

      <Section title="Cartões">
        <div className={styles.grid4}>
          <StatCard label="Usuários ativos" value="12" series={[3, 3, 4, 4, 5, 5, 6, 6, 7]} footer="1 convite pendente" delta={{ text: '+1', direction: 'up' }} />
          <StatCard label="Sessões em setembro" value="38" series={[4, 6, 5, 7, 6, 8, 7, 9, 8]} footer="desde agosto" delta={{ text: '+19%', direction: 'up' }} />
          <StatCard label="Aguardando dados" value="1" tone="warning" series={[0, 0, 1, 0, 0, 2, 0, 0, 1]} footer="Paisagens naturais" highlight="em envio" />
          <StatCard label="Registros na auditoria hoje" value="7" series={[3, 4, 3, 5, 4, 6, 5, 6, 5]} footer="o último às 14:31" delta={{ text: '+2', direction: 'up' }} />
        </div>
        <Card title="Informações" actions={<Button variant="secondary" size="sm">Editar informações</Button>}>
          <p className={styles.muted}>Os dados coletados não podem ser alterados. Qualquer mudança nas informações fica registrada na auditoria.</p>
        </Card>
        <DangerZone
          title="Inativar paciente"
          description="O cadastro sai das listas e não recebe novas sessões. As sessões e os dados coletados continuam guardados."
          actionLabel="Inativar paciente"
          onAction={() => toast.error('Exemplo de erro: não foi possível inativar.')}
        />
      </Section>

      <Section title="Envio de arquivos">
        <Dropzone
          accept=".jpg,.jpeg,.png,.mp4"
          title="Arraste imagens e vídeos para cá"
          description="Formatos aceitos: JPG, PNG e MP4."
          onFiles={(files) => setDropped(files.map((f) => f.name))}
        />
        {dropped.length > 0 && <p className={styles.muted}>Recebidos: {dropped.join(', ')}</p>}
        <div className={styles.uploads}>
          <UploadItem name="cachoeira-na-mata.jpg" size={2.4 * 1024 * 1024} status="done" selected onSelect={() => undefined} />
          <UploadItem name="trilha-no-bosque.mp4" size={86 * 1024 * 1024} status="uploading" progress={0.64} onSelect={() => undefined} />
          <UploadItem name="video-bruto.mov" status="error" error="Formato não aceito. Envie o vídeo em MP4." onRemove={() => undefined} />
        </div>
        <div className={styles.narrow}>
          <ProgressBar value={1} tone="success" size="md" label="Estímulos no óculos" />
        </div>
      </Section>

      <Section title="Modal e avisos">
        <div className={styles.row}>
          <Button variant="secondary" icon={Upload} onClick={() => setModalOpen(true)}>
            Abrir modal
          </Button>
          <Button variant="secondary" onClick={() => toast.success('Paciente cadastrado.')}>
            Aviso de sucesso
          </Button>
          <Button variant="secondary" onClick={() => toast.error('Não foi possível salvar. Tente de novo.')}>
            Aviso de erro
          </Button>
        </div>
        <FormAlert>E-mail ou senha incorretos.</FormAlert>
        <Modal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title="Visibilidade da sessão"
          subtitle="Rostos neutros e expressivos, paciente P-015"
          size="sm"
          footerNote="A mudança fica registrada na auditoria."
          footer={
            <>
              <Button variant="secondary" size="sm" onClick={() => setModalOpen(false)}>
                Cancelar
              </Button>
              <Button size="sm" onClick={() => setModalOpen(false)}>
                Salvar
              </Button>
            </>
          }
        >
          <RadioCardGroup legend="Quem pode ver" layout="stack">
            <RadioCard name="vis" value="owner" label="Só o responsável" description="Apenas Ana Souza vê a sessão e os dados coletados." defaultChecked />
            <RadioCard name="vis" value="shared" label="Pesquisadores escolhidos" description="Ana Souza e os pesquisadores marcados abaixo." />
            <RadioCard name="vis" value="all" label="Todos os pesquisadores" description="Qualquer pesquisador com acesso ao sistema." />
          </RadioCardGroup>
        </Modal>
      </Section>

      <Section title="Menu lateral e painel da marca">
        <div className={styles.frames}>
          <div className={styles.sidebarFrame}>
            <AtLocation path="/">
              <Sidebar user={{ name: 'Ana Souza', roleLabel: 'Pesquisador' }} sessionsBadge={2} />
            </AtLocation>
          </div>
          <div className={styles.panelFrame}>
            <BrandPanel />
          </div>
        </div>
      </Section>
    </div>
  )
}
