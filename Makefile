.PHONY: setup check data eda sample enrich enrich-carregar index eval eval-smoke app

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
	@echo "ainda não implementado — ver specs/03-rag-knowledge-base.md"; exit 1

eval:
	@echo "ainda não implementado — ver specs/06-evals.md"; exit 1

eval-smoke:
	@echo "ainda não implementado — ver specs/06-evals.md"; exit 1

app:
	uv run uvicorn app.main:app --reload
