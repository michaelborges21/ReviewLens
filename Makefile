.PHONY: setup check data enrich index eval eval-smoke app

setup:
	uv sync
	uv run pre-commit install

check:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src/
	uv run pytest -q

data:
	uv run python -m bri.data.ingest

enrich:
	@echo "ainda não implementado — ver specs/02-nlp-pipeline.md"; exit 1

index:
	@echo "ainda não implementado — ver specs/03-rag-knowledge-base.md"; exit 1

eval:
	@echo "ainda não implementado — ver specs/06-evals.md"; exit 1

eval-smoke:
	@echo "ainda não implementado — ver specs/06-evals.md"; exit 1

app:
	@echo "ainda não implementado — ver specs/04-qa-agent.md"; exit 1
