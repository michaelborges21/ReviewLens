.PHONY: setup check data eda sample enrich enrich-carregar index resumir resumir-carregar \
        topicos topicos-medir topicos-carregar eval eval-smoke golden-comparar \
        golden-gerar red-team app docker-up docker-up-cpu docker-down docker-logs \
        docker-data docker-modelos

setup:
	uv sync
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

check:
	uv run ruff check src tests app evals
	uv run ruff format --check src tests app evals
	uv run mypy
	uv run pytest -q

data:
	uv run python -m bri.data.ingest
	uv run python -m bri.data.process
	uv run python -m bri.data.stats

eda:
	uv run python -m bri.data.eda

sample:
	uv run python -m bri.nlp.sampling

enrich:
	uv run python -m bri.nlp.extract $(if $(LIMITE),--limite $(LIMITE))

enrich-carregar:
	uv run python -m bri.nlp.extract --carregar

index:
	uv run python -m bri.retrieval.indexar

resumir:
	uv run python -m bri.nlp.sumarizar $(if $(LIMITE),--limite $(LIMITE))

resumir-carregar:
	uv run python -m bri.nlp.sumarizar --carregar

topicos-medir:
	uv run python -m bri.nlp.topicos --medir

topicos:
	uv run python -m bri.nlp.topicos $(if $(K),--k $(K))

topicos-carregar:
	uv run python -m bri.nlp.topicos --carregar

eval:
	@echo "ainda não implementado — ver specs/06-evals.md"; exit 1

eval-smoke:
	uv run python -m evals.smoke_narracao

# GABARITO= troca o CSV anotado; SAIDA= grava o relatório em arquivo em vez da tela
golden-comparar:
	uv run python -m evals.comparar_aspectos \
		$(if $(GABARITO),--gabarito $(GABARITO)) $(if $(SAIDA),--saida $(SAIDA))

golden-gerar:
	uv run python -m evals.gerar_golden_aspectos

red-team:
	uv run python -m evals.red_team

app:
	uv run uvicorn app.main:app --reload

# --- Docker (ADR-022) -------------------------------------------------------------------------
# Com GPU por padrão, que é o caso desta máquina. Sem placa NVIDIA, use os alvos *-cpu.
COMPOSE_GPU = docker compose -f docker-compose.yml -f docker-compose.gpu.yml

docker-up:
	$(COMPOSE_GPU) up -d --build

docker-up-cpu:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# Constrói o banco a partir dos CSVs de data/raw/ sem precisar de Python no host.
docker-data:
	$(COMPOSE_GPU) run --rm app make data

# Baixa os modelos sem subir o app — útil para deixar o download rodando antes.
docker-modelos:
	$(COMPOSE_GPU) up -d ollama
	$(COMPOSE_GPU) run --rm baixar-modelos
