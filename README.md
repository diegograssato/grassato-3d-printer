# Grassato's 3D — Sistema de Gestão

Sistema web completo para gestão de negócio de impressão 3D, desenvolvido com **Django 4.2**, **Celery**, **Redis** e **Poetry**.

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
| **Integrações ML** | Publicação de produtos no MercadoLivre via OAuth2, upload de fotos, notificações IPN assíncronas |

---

## Integrações — MercadoLivre

### OAuth2
1. Cadastre uma integração em **Integrações → Nova Integração** com seu `client_id` e `client_secret`.
2. Clique em **Autorizar** para iniciar o fluxo OAuth2. O callback é processado de forma assíncrona via Celery.

### Publicar produto
1. Na lista de produtos, clique em **Publicar no ML**.
2. Informe a **Categoria ML** (ex.: `MLB268508`), preencha os atributos obrigatórios e faça o **upload de fotos** (mínimo 2).
3. A **primeira foto** é automaticamente a capa do anúncio. Arraste para reordenar.

### Notificações IPN (webhooks)
O endpoint `/integracoes/ml/notificacao/` recebe:
- `orders_v2` / `orders` → processa pedido na fila `ml_orders`
- `items` / `item_status` / `item_price` → processa atualização de produto na fila `ml_status`

### Upload de fotos
- Mínimo 2 fotos por anúncio (capa obrigatória + 1 adicional)
- Formatos aceitos: JPEG, PNG, WebP
- Tamanho máximo por imagem: 10 MB
- Suporte a drag-and-drop e reordenação visual
- As imagens são salvas em `/media/integracoes/imagens/` e servidas pelo Nginx

---

## Automações via Signals Django

- Venda registrada → decrementa `Produto.estoque_quantidade` e `Filamento.peso_disponivel_g`
- Venda registrada → cria `MovimentacaoCaixa` (ENTRADA) automaticamente
- Compra de filamento → cria `MovimentacaoCaixa` (SAÍDA) automaticamente
- Produto publicado no ML → salva `sku_externo` e `status_externo`

---

## Processamento Assíncrono (Celery + Redis)

Todas as operações com o MercadoLivre são processadas de forma assíncrona para garantir resposta rápida e resiliência.

| Fila | Task | Finalidade |
|---|---|---|
| `ml_oauth` | `processar_oauth_ml` | Troca o `code` pelo token OAuth2 |
| `ml_orders` | `processar_pedido_ml` | Processa novos pedidos |
| `ml_status` | `processar_status_ml` | Atualiza status de produtos |

- **Retry automático** com backoff exponencial (máx. 3–5 tentativas)
- **Monitoramento** via Celery Flower em `http://localhost:5555`
- Em desenvolvimento (`DEBUG=True`): tasks executam de forma síncrona (`CELERY_TASK_ALWAYS_EAGER=True`)

---

## Stack Técnica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.12 + Django 4.2 |
| Servidor WSGI | Gunicorn |
| Fila de tarefas | Celery 5.6 + Redis 7 |
| Cache / Sessões | Redis (DB 0) |
| Broker / Result | Redis (DB 1) |
| Banco de dados | MySQL 8.0 (produção) / SQLite (dev) |
| Upload de imagens | Pillow 11 |
| Monitoramento Celery | Flower 2.0 |
| Proxy reverso | Nginx 1.27 |
| Containerização | Docker + Docker Compose |
| Gerenciador de deps | Poetry |

---

## Rodando localmente (SQLite, sem Docker)

```bash
# Instala dependências
poetry install

# Cria banco e superusuário
poetry run python manage.py migrate
poetry run python manage.py createsuperuser

# Inicia o servidor
poetry run python manage.py runserver
```

Acesse em `http://localhost:8000`. Login com as credenciais criadas.

> Em desenvolvimento, as tasks Celery rodam de forma síncrona — não é necessário Redis/Celery rodando.

---

## Rodando com Docker Compose (produção)

### Pré-requisitos
- Docker ≥ 24 e Docker Compose V2
- Arquivo `.env` na raiz (veja `.env.example`)

### Subir todos os serviços

```bash
docker compose up -d --build
```

### Serviços disponíveis

| Serviço | URL |
|---|---|
| Aplicação | `http://localhost` (via Nginx) |
| Flower (Celery) | `http://localhost:5555` |

### Variáveis de ambiente essenciais (`.env`)

```dotenv
SECRET_KEY=sua-chave-secreta-longa
DB_NAME=grassato3d
DB_USER=grassato
DB_PASSWORD=senha_db
DB_ROOT_PASSWORD=senha_root

# Superusuário criado automaticamente na primeira inicialização
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@exemplo.com
DJANGO_SUPERUSER_PASSWORD=senha_admin

# Flower
FLOWER_USER=admin
FLOWER_PASSWORD=senha_flower

# ngrok / domínio público para callbacks do ML
SITE_URL=https://seu-dominio.ngrok-free.app
```

### Comandos úteis

```bash
# Ver logs da aplicação
docker compose logs -f app

# Ver logs do worker Celery
docker compose logs -f celery

# Monitorar filas no Flower
open http://localhost:5555

# Rodar migrations manualmente
docker compose exec app python manage.py migrate

# Gerar novas migrations
docker compose exec app python manage.py makemigrations
```

---

## Estrutura do Projeto

```
grassato-3d/
├── config/                  # Configurações Django + Celery
├── caixa/                   # Módulo caixa/financeiro
├── dashboard/               # Dashboard e balancete
├── estoque/                 # Filamentos e produtos
├── integracoes/             # MercadoLivre + Celery tasks
│   ├── services/            # Cliente da API ML
│   ├── tasks.py             # Tasks assíncronas Celery
│   └── migrations/
├── vendas/                  # Registro de vendas
├── templates/               # Templates HTML (Bootstrap 5)
├── staticfiles/             # Static files coletados
├── media/                   # Uploads de imagens (prod: volume Docker)
├── docker-compose.yaml
├── Dockerfile
├── nginx.conf
├── pyproject.toml
└── manage.py
```

---

## Kubernetes (k8s/)

A pasta `k8s/` contém manifestos para deploy no **Azure Kubernetes Service (AKS)**:

- `namespace.yaml` — namespace `grassato`
- `configmap.yaml` — variáveis de configuração
- `secret.yaml` — credenciais sensíveis (base64)
- `deployment.yaml` — Deployment da aplicação
- `hpa.yaml` — HorizontalPodAutoscaler
- `ingress.yaml` — Ingress NGINX
- `infra.yaml` — serviços de infraestrutura

---

## Licença

Projeto proprietário — Grassato Impressão 3D.
