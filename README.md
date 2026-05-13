# Grassato's 3D — Sistema de Gestão

Sistema web completo para gestão de negócio de impressão 3D, desenvolvido com **Django 4.2** e **Poetry**.

---

## Funcionalidades

| Módulo | Descrição |
|---|---|
| **Filamentos** | Cadastro com controle de peso disponível, status de estoque (OK / Baixo / Crítico) e lançamento automático de compra no caixa |
| **Produtos** | Cadastro com consumo de filamento por peça (g e m), tempo de impressão e cálculo de margem de lucro |
| **Vendas** | Registro de vendas com validação de estoque; ao salvar: decrementa produto + filamento e cria entrada no caixa automaticamente |
| **Caixa** | Controle de entradas e saídas com filtros por mês/tipo, saldo acumulado e lançamentos manuais |
| **Dashboard** | Cards com receita, despesas, lucro e saldo do mês; gráfico de barras (6 meses); alertas de estoque crítico |
| **Balancete** | Tabela mensal com faturamento, entradas, saídas, resultado e saldo acumulado (12 meses) |

### Automações via signals Django
- Venda registrada → decrementa `Produto.estoque_quantidade` e `Filamento.peso_disponivel_g`
- Venda registrada → cria `MovimentacaoCaixa` (ENTRADA) automaticamente
- Venda excluída → reverte estoque do produto e do filamento
- Filamento cadastrado → cria `MovimentacaoCaixa` (SAÍDA/Compra de Filamento) automaticamente

---

## Stack

- **Backend:** Python 3.11+, Django 4.2, Gunicorn
- **Banco de dados:** SQLite (dev) · MySQL 8 (prod)
- **Cache / Sessões:** Redis 7 (opcional, ativado via `REDIS_URL`)
- **Frontend:** Bootstrap 5.3 + Bootstrap Icons + Chart.js (via CDN)
- **Static files:** WhiteNoise
- **Gerenciador de dependências:** Poetry

---

## Estrutura do Projeto

```
grassato-3d/
├── config/               # Settings, URLs, WSGI
├── estoque/              # App: Filamentos e Produtos
├── vendas/               # App: Vendas + Signals
├── caixa/                # App: Controle de Caixa
├── dashboard/            # App: Dashboard e Balancete
├── templates/            # Templates HTML (Bootstrap 5)
├── k8s/                  # Manifests Kubernetes
├── Dockerfile
├── docker-compose.yaml
├── nginx.conf
└── pyproject.toml
```

---

## Desenvolvimento Local

### Pré-requisitos
- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)

### Instalação

```bash
# 1. Clonar o repositório
git clone <url-do-repositorio>
cd grassato-3d

# 2. Instalar dependências
poetry install --no-root

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env conforme necessário

# 4. Criar banco e aplicar migrações
poetry run python manage.py migrate

# 5. Criar superusuário (painel admin)
poetry run python manage.py createsuperuser

# 6. Iniciar servidor
poetry run python manage.py runserver
```

Acesse: **http://localhost:8000**  
Painel admin: **http://localhost:8000/admin**

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `SECRET_KEY` | *(insecure dev key)* | Chave secreta do Django |
| `DEBUG` | `True` | Modo debug |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts permitidos |
| `DB_ENGINE` | `sqlite3` | `sqlite3` ou `mysql` |
| `DB_NAME` | `grassato3d` | Nome do banco |
| `DB_USER` | `grassato` | Usuário do banco |
| `DB_PASSWORD` | *(vazio)* | Senha do banco |
| `DB_HOST` | `127.0.0.1` | Host do banco |
| `DB_PORT` | `3306` | Porta do banco |
| `REDIS_URL` | *(vazio)* | URL do Redis — ex: `redis://localhost:6379/0` |
| `GUNICORN_WORKERS` | `2` | Workers do Gunicorn |
| `GUNICORN_THREADS` | `4` | Threads por worker |

---

## Docker Compose (Produção local)

Sobe o stack completo: **MySQL 8 + Redis 7 + Django/Gunicorn + Nginx**.

```bash
# Copiar e ajustar variáveis
cp .env.example .env
# Edite: SECRET_KEY, DB_PASSWORD, DB_ROOT_PASSWORD

# Build e subir
docker compose up -d --build

# Acompanhar logs
docker compose logs -f app
```

Acesse: **http://localhost**

### Serviços

| Serviço | Porta | Descrição |
|---|---|---|
| `nginx` | `80` | Proxy reverso + static files |
| `app` | `8000` (interno) | Django + Gunicorn |
| `db` | `3306` (interno) | MySQL 8 |
| `redis` | `6379` (interno) | Redis 7 |

---

## Kubernetes

Os manifests estão em `k8s/`. A aplicação usa `ConfigMap` para configurações e `Secret` para credenciais.

### Ordem de aplicação

```bash
# 1. Namespace
kubectl apply -f k8s/namespace.yaml

# 2. Secrets (edite as senhas antes!)
kubectl apply -f k8s/secret.yaml

# 3. ConfigMap (ajuste host/domínio)
kubectl apply -f k8s/configmap.yaml

# 4. Infraestrutura (MySQL StatefulSet + Redis)
kubectl apply -f k8s/infra.yaml

# 5. Aplicação
kubectl apply -f k8s/deployment.yaml

# 6. Ingress
kubectl apply -f k8s/ingress.yaml

# 7. HPA (auto-scaling)
kubectl apply -f k8s/hpa.yaml
```

### Arquitetura K8s

```
Internet
   │
   ▼
Ingress (nginx)
   │
   ▼
grassato-service (ClusterIP :80)
   │
   ▼
grassato-app (Deployment, 2–6 réplicas)
   │           │
   ▼           ▼
mysql-service  redis-service
(StatefulSet)  (Deployment)
```

### Manifests

| Arquivo | Recurso | Descrição |
|---|---|---|
| `namespace.yaml` | Namespace | `grassato-3d` |
| `configmap.yaml` | ConfigMap | Variáveis de ambiente (não-sensíveis) |
| `secret.yaml` | Secret | SECRET_KEY, DB_USER, DB_PASSWORD |
| `deployment.yaml` | Deployment + Service | App Django; init container executa `migrate` |
| `infra.yaml` | StatefulSet + Deployments | MySQL 8 e Redis 7 com Services |
| `ingress.yaml` | Ingress | Roteamento HTTP/HTTPS (suporte a cert-manager) |
| `hpa.yaml` | HorizontalPodAutoscaler | Escala de 2 a 6 réplicas por CPU/memória |

### Build e push da imagem

```bash
# Build
docker build -t seu-registry/grassato-3d:latest .

# Push
docker push seu-registry/grassato-3d:latest

# Atualizar imagem no cluster
kubectl set image deployment/grassato-app \
  grassato-app=seu-registry/grassato-3d:latest \
  -n grassato-3d
```

> **Atenção:** substitua `seu-registry/grassato-3d` pela URL do seu registry (Docker Hub, GCR, ECR, etc.) em `k8s/deployment.yaml` antes de aplicar.

---

## Rotas da Aplicação

| URL | Módulo | Descrição |
|---|---|---|
| `/` | Dashboard | Dashboard geral |
| `/balancete/` | Dashboard | Balancete mensal (12 meses) |
| `/estoque/filamentos/` | Estoque | Listagem de filamentos |
| `/estoque/filamentos/novo/` | Estoque | Cadastrar filamento |
| `/estoque/produtos/` | Estoque | Listagem de produtos |
| `/estoque/produtos/novo/` | Estoque | Cadastrar produto |
| `/vendas/` | Vendas | Listagem de vendas |
| `/vendas/nova/` | Vendas | Registrar venda |
| `/caixa/` | Caixa | Controle de caixa |
| `/caixa/nova/` | Caixa | Lançamento manual |
| `/admin/` | Admin | Painel administrativo Django |

---

## Licença

Uso interno — Grassato's 3D.
