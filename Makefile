.DEFAULT_GOAL := help
.PHONY: help dev migrate superuser shell lint test \
        docker-build docker-up docker-down docker-logs docker-shell docker-clean

# ── Variáveis ─────────────────────────────────────────────────────────────────
IMAGE      ?= grassato-3d-printer
TAG        ?= local
COMPOSE    := docker compose
PORT       ?= 8000

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' \
		| sort

# ── Desenvolvimento local ─────────────────────────────────────────────────────
dev: ## Inicia servidor Django em modo desenvolvimento (localhost:$(PORT))
	poetry run python manage.py runserver 0.0.0.0:$(PORT)

migrate: ## Aplica migrações do banco de dados
	poetry run python manage.py migrate

makemigrations: ## Gera novas migrações
	poetry run python manage.py makemigrations

superuser: ## Cria superusuário interativamente
	poetry run python manage.py createsuperuser

shell: ## Abre o Django shell
	poetry run python manage.py shell

check: ## Executa o Django system check
	poetry run python manage.py check

lint: ## Roda flake8 (requer dev dependencies)
	poetry run flake8 .

test: ## Executa a suite de testes
	poetry run python manage.py test

collectstatic: ## Coleta arquivos estáticos
	poetry run python manage.py collectstatic --noinput

# ── Docker (imagem isolada) ───────────────────────────────────────────────────
docker-build: ## Constrói a imagem Docker (IMAGE:TAG)
	docker build -t $(IMAGE):$(TAG) .

docker-run: ## Sobe container único para smoke-test rápido
	docker run --rm \
		-p $(PORT):8000 \
		-e SECRET_KEY=dev-only-not-for-production \
		-e DB_ENGINE=sqlite3 \
		-e DB_NAME=/tmp/dev.sqlite3 \
		-e DEBUG=True \
		$(IMAGE):$(TAG)

# ── Docker Compose ────────────────────────────────────────────────────────────
up: ## Sobe todos os serviços em background (build automático)
	$(COMPOSE) up --build -d

up-fg: ## Sobe todos os serviços em foreground (logs no terminal)
	$(COMPOSE) up --build

down: ## Para e remove todos os containers
	$(COMPOSE) down

down-v: ## Para containers e remove volumes (apaga dados!)
	$(COMPOSE) down -v

restart: ## Reinicia todos os serviços
	$(COMPOSE) restart

logs: ## Exibe logs de todos os serviços (Ctrl+C para sair)
	$(COMPOSE) logs -f

logs-app: ## Exibe apenas logs do serviço app
	$(COMPOSE) logs -f app

ps: ## Lista status dos containers
	$(COMPOSE) ps

docker-shell: ## Abre shell bash dentro do container app
	$(COMPOSE) exec app sh

docker-clean: ## Remove imagens locais e volumes órfãos
	docker image rm -f $(IMAGE):$(TAG) 2>/dev/null || true
	docker volume prune -f
	@echo "Limpeza concluída."
