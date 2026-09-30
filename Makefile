.PHONY: setup check data eda sample enrich enrich-carregar index resumir resumir-carregar \
        topicos topicos-medir topicos-carregar eval eval-smoke red-team app

setup:
	uv sync
	uv run pre-commit install

check:
	uv run ruff check src tests app
	uv run ruff format --check src tests app
	uv run mypy src/
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

red-team:
	uv run python -m evals.red_team

app:
	uv run uvicorn app.main:app --reload
