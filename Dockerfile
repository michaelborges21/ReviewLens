# Imagem só da aplicação. Modelo de IA e CSVs ficam FORA de propósito (ADR-022):
#   - modelo: ~8,8GB, baixado pelo serviço `baixar-modelos` para um volume do Docker
#   - CSVs: baixados do Drive para data/raw/ no host, que o compose monta
# Sem isso a imagem passaria de 16GB e todo rebuild reempacotaria dado que nunca muda.
FROM python:3.12-slim

# uv pela imagem oficial: um COPY, sem pip install e sem cache de pip na camada.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    # os alvos do Makefile chamam `uv run`, que por padrão re-sincroniza o ambiente e exigiria
    # rede em tempo de execução. Aqui o ambiente já está pronto: usa como está.
    UV_NO_SYNC=1 \
    PATH="/app/.venv/bin:$PATH"

# Dependências antes do código: só o lockfile invalida esta camada, então editar src/ não
# refaz a instalação.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY app/ ./app/
COPY evals/ ./evals/
COPY Makefile ./
RUN uv sync --frozen --no-dev

# Montados pelo compose; criados aqui para o app subir mesmo sem volume, em vez de estourar.
RUN mkdir -p data/raw data/interim data/processed reports/exports

EXPOSE 8000

# Sem --reload: recarregar a cada mudança de arquivo serve ao desenvolvimento, não a quem só
# quer o sistema de pé.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
