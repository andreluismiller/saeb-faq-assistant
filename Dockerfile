FROM python:3.12-slim

# libgomp1: dependência de runtime do onnxruntime (usado pelo FastEmbed)
# curl: usado apenas para healthcheck do container
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala o uv (mesmo gerenciador de pacotes já usado no projeto)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copia primeiro apenas os manifestos de dependências para aproveitar o cache
# de camadas do Docker (só reinstala dependências se pyproject/uv.lock mudarem)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Agora copia o restante do código-fonte
COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]