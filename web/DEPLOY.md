# Deploy na VM da faculdade — passo a passo

Objetivo: subir **site + API + banco** numa VM Linux para que o **óculos envie sessões de
qualquer lugar** e você visualize de qualquer navegador.

```
[Quest Pro, em qualquer rede] --HTTP--> http://SEU-SERVIDOR:8000/api/v1/sessions  (com X-Api-Key)
[Seu navegador]              --------> http://SEU-SERVIDOR:8000/                  (site)
```

> **Fase 3 (sessões configuradas no site):** a ingestão do fluxo antigo (`POST /api/v1/sessions`,
> `/frames`, `/complete`) e o `scripts/replay_session.py` saíram. O app atual do óculos não consegue
> mais enviar até o app novo (Fase 7), e os passos 5.4 e 6 abaixo ficam sem efeito até lá. As
> sessões antigas continuam no banco (tabela `legacy_sessions`), só para leitura em
> `/api/v1/legacy/sessions`. O roteiro completo do deploy é refeito na Fase 8.
>
> **Fase 4 (execução ao vivo):** o óculos e o navegador falam pelo servidor por WebSocket, e o hub
> que liga os dois fica em memória: a execução ao vivo só funciona com **um** worker. O `Dockerfile`
> ainda sobe com `--workers 2` (a troca, o proxy com WebSocket e TLS são da Fase 8); até lá, para
> testar no servidor, rode com `--workers 1`. Defina também `QUESTPRO_DEVICE_KEY` no `.env` (a chave
> que o óculos manda; vazia, qualquer um se conecta como óculos).

---

## 0. O que pedir/confirmar com a TI da faculdade (ANTES de tudo)

1. **VM Linux** (Ubuntu 22.04+ recomendado) com acesso `sudo` via SSH.
2. **Recursos**: 2 vCPU, 4 GB RAM e **≥ 50 GB de disco** (cada minuto de sessão a 30 fps ≈ 150–170 MB de frames + MP4; o disco é o recurso que acaba primeiro).
3. **IP fixo ou hostname** para a VM.
4. **Liberação de firewall**: a porta **8000/TCP** (ou 80) precisa aceitar conexões **da internet**, não só da rede do campus — senão o óculos só envia quando estiver na faculdade. Pergunte literalmente: *“essa VM aceita conexão TCP entrante da internet na porta 8000?”*
   - Se só liberarem dentro do campus/VPN, o sistema funciona, mas o óculos precisa estar na rede/VPN da faculdade para enviar.
5. **Docker + Docker Compose** instalados (ou permissão para instalar).

## 1. Instalar o Docker (se não vier instalado)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # sair e entrar de novo no SSH depois disso
docker --version && docker compose version
```

## 2. Colocar o projeto na VM

```bash
# Só a pasta web/: o servidor não precisa dos assets do Unreal (~330 MB em LFS).
GIT_LFS_SKIP_SMUDGE=1 git clone --filter=blob:none --sparse https://github.com/joaozanini/NeuroSight.git
cd NeuroSight && git sparse-checkout set web && cd web
# (alternativa sem git: scp -r da pasta do projeto pro servidor)
```

## 3. Configurar o `.env`

```bash
cp .env.example .env
nano .env
```

Defina **obrigatoriamente**:
```ini
QUESTPRO_API_KEY=uma-chave-longa-e-aleatoria-aqui     # ex.: sair de `openssl rand -hex 24`
QUESTPRO_DB_PASSWORD=outra-senha-forte
QUESTPRO_HTTP_PORT=8000
QUESTPRO_PUBLIC_BASE_URL=http://IP-DO-SERVIDOR:8000      # endereço do site, vai nos links dos e-mails
```
> A `QUESTPRO_API_KEY` protege a leitura das sessões antigas (`/api/v1/legacy/sessions`, que também
> aceita o login do site). Sem ela definida essa leitura fica **aberta na internet** — não faça isso.

Para os convites e as redefinições de senha saírem por e-mail, defina também o SMTP
(`QUESTPRO_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_FROM` e `_SECURITY`; veja o
`.env.example`). Sem SMTP o site funciona igual: o admin copia o link na tela.

## 4. Subir

```bash
docker compose up -d --build     # 1ª vez demora (build do front + imagem)
docker compose ps                # os 2 serviços "running/healthy"
docker compose logs -f app       # logs da API (Ctrl+C pra sair)
```

Ao subir, a API aplica as migrações do banco (Alembic). Na primeira subida de uma versão com
Alembic, o banco que já existia é reconhecido e carimbado na baseline, sem recriar nada (o log
mostra `banco anterior ao Alembic: carimbando a baseline 0001_baseline`). Para conferir a versão
do banco: `docker compose exec app alembic current`.

O site exige login. Crie o primeiro admin uma vez (o link do convite aparece no terminal):

```bash
docker compose exec app python -m app.seed --admin-email voce@lab.br --admin-name "Seu Nome"
```

Se o log da API avisar que os links apontam para `localhost`, falta a `QUESTPRO_PUBLIC_BASE_URL`
no `.env` (depois de mudar o `.env`, rode `docker compose up -d` de novo).

## 5. Testar (nesta ordem — cada passo isola uma camada)

```bash
# 5.1 na própria VM:
curl http://localhost:8000/healthz          # -> {"ok":true}

# 5.2 do SEU PC (testa firewall interno):
curl http://IP-DA-VM:8000/healthz

# 5.3 do seu CELULAR NO 4G, no navegador (testa exposição à internet — o teste que importa!):
#     http://IP-DA-VM:8000  -> deve abrir o site "NeuroSight"
```
Se 5.1 funciona e 5.3 não → é firewall da faculdade (volte ao passo 0.4).

5.4 (execução de ponta a ponta): rode o simulador do óculos de qualquer máquina com o repositório e o
venv do backend (ele usa o gerador de `backend/app/synthetic.py`), apontando para o servidor
(`python scripts/device_simulator.py --server http://IP-DA-VM:8000 --key SUA-CHAVE`), e prepare uma
sessão pelo site (ver `web/README.md`, "Testar sem o óculos"). Depois do B, a sessão fica Concluída
e a análise aparece em "Analisar dados".

## 6. Apontar o app do óculos pro servidor

No editor UE, selecione o **GazeRecorderActor** na cena → painel **Details** → categoria **Upload**:

| Campo | Valor |
|---|---|
| **Upload Url** | `http://IP-DA-VM:8000/api/v1/sessions` |
| **Api Key** | a mesma `QUESTPRO_API_KEY` do `.env` |

Salve o level (Ctrl+S) e **reempacote o APK** (Platforms → Android ASTC → Package Project).
Não precisa mexer em código — os valores da instância valem sobre o default.

> Dica para sessões longas fora do campus: upload de 1 min de sessão ≈ 150 MB. Numa rede
> lenta isso demora. Se necessário, reduza `Video Fps` (ex.: 15) e/ou `Frame Width/Height`
> (ex.: 768) no mesmo painel Details — sem recompilar.

## 7. Operação do dia a dia

```bash
docker compose logs -f app                     # acompanhar uploads chegando
docker compose restart app                     # reiniciar só a API
git pull && docker compose up -d --build       # atualizar o sistema (dentro de NeuroSight/web)
docker system df                               # uso de disco do docker
```

**Backup** (banco + mídia):
```bash
docker compose exec db pg_dump -U questpro questpro > backup_$(date +%F).sql
docker run --rm -v questpro-eyetracking-web_media:/m -v $PWD:/out alpine tar czf /out/media_$(date +%F).tgz -C /m .
```

---

## Alternativa sem Docker (se a TI não permitir)

```bash
sudo apt install -y python3.12-venv nodejs npm postgresql
# banco
sudo -u postgres psql -c "CREATE USER questpro PASSWORD 'senha'; CREATE DATABASE questpro OWNER questpro;"
# frontend
cd frontend && npm ci && npm run build && cd ..
# backend
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
QUESTPRO_DB_URL=postgresql+psycopg://questpro:senha@localhost:5432/questpro \
QUESTPRO_STATIC_DIR=../frontend/dist \
QUESTPRO_MEDIA_ROOT=/var/lib/questpro/media \
QUESTPRO_API_KEY=sua-chave \
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```
Para rodar como serviço, crie um systemd unit com esse comando (`ExecStart`) e as mesmas
variáveis (`Environment=`). Se colocar **nginx** na frente, configure:
`client_max_body_size 100M;` e `proxy_read_timeout 300s;` (os lotes de frames têm ~2 MB e
o vídeo pode demorar a servir), com `proxy_pass http://127.0.0.1:8000;`.

## HTTPS (opcional, recomendado se tiver um domínio)

Com um domínio apontando pra VM, o jeito mais simples é o **Caddy** na frente (TLS automático):
```bash
sudo apt install -y caddy
# /etc/caddy/Caddyfile:
#   seu-dominio.br {
#       reverse_proxy 127.0.0.1:8000
#   }
sudo systemctl restart caddy
```
Aí o `Upload Url` do óculos vira `https://seu-dominio.br/api/v1/sessions` (porta 443, que
costuma estar liberada em qualquer rede).

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| 5.1 ok, 5.3 falha | firewall da faculdade não liberou a porta pra internet |
| upload do óculos falha com 401 | `Api Key` do Details ≠ `QUESTPRO_API_KEY` do `.env` |
| sessão fica em `processing` pra sempre | veja `docker compose logs app` (erro na montagem do MP4) |
| disco cheio | aumente o disco (a limpeza de sessões antigas pelo site ainda não existe) |
