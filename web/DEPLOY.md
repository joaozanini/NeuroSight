# Deploy na VM da faculdade — passo a passo

Objetivo: subir **site + API + banco** numa VM Linux para que o **óculos envie sessões de
qualquer lugar** e você visualize de qualquer navegador.

```
[Quest Pro, em qualquer rede] --HTTP--> http://SEU-SERVIDOR:8000/api/v1/sessions  (com X-Api-Key)
[Seu navegador]              --------> http://SEU-SERVIDOR:8000/                  (site)
```

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
```
> A `QUESTPRO_API_KEY` protege o upload e o delete. Sem ela definida a API fica **aberta na
> internet** — não faça isso.

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
docker compose exec -e QUESTPRO_PUBLIC_BASE_URL=http://SEU-SERVIDOR:8000 app \
  python -m app.seed --admin-email voce@lab.br --admin-name "Seu Nome"
```

> Até a Fase 8 do plano, o `docker-compose.yml` não repassa as variáveis de e-mail e de endereço
> do site (`QUESTPRO_SMTP_*`, `QUESTPRO_PUBLIC_BASE_URL`): os convites que o admin cria pelo site
> mostram um link com `localhost:5173`, que precisa ter o endereço trocado à mão.

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

```bash
# 5.4 ingestão de ponta a ponta, do seu PC (Windows), com uma sessão real já gravada:
py -3.12 scripts\replay_session.py "C:\GitHub\NeuroSight\headset\Saved\GazeSessions\2026-06-17_22-10-54" ^
    --api http://IP-DA-VM:8000/api/v1 --api-key SUA-CHAVE
# -> create / frames / complete / status: complete / codec=h264
# e a sessão aparece em http://IP-DA-VM:8000
```

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
| `uploading` eterno sem frames | óculos perdeu rede no meio; reenvie com `replay_session.py` (retoma de onde parou) |
| disco cheio | apague sessões antigas pelo site (ou aumente o disco) |
