FROM python:3.12-slim

WORKDIR /app

# Instala o uv (gerenciador de dependências do projeto)
RUN pip install uv

# Copia os arquivos de configuração e dependências
COPY pyproject.toml uv.lock Makefile README.md ./
COPY src /app/src
COPY app /app/app

# Instala as dependências (sem as de dev)
RUN uv sync --no-dev

# Garante que os diretórios de dados e logs existam
RUN mkdir -p data/processed reports

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Inicia a aplicação FastAPI
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
