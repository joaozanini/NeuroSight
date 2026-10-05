import LinkButton from '../components/Button/LinkButton'
import PageHeader from '../components/PageHeader/PageHeader'
import { usePageTitle } from '../lib/usePageTitle'

export default function ForbiddenPage() {
  usePageTitle('Sem acesso')
  return (
    <>
      <PageHeader
        title="Sem acesso"
        subtitle="Seu perfil não tem permissão para ver esta página. Se precisar dela, fale com o administrador do sistema."
      />
      <LinkButton to="/" variant="secondary">
        Voltar para o início
      </LinkButton>
    </>
  )
}
