FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first, in their own layer, so editing source code
# doesn't bust the dependency-install cache on rebuild.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src/ ./src/
COPY docs/ ./docs/
COPY data/ ./data/
RUN uv sync --frozen

EXPOSE 8000
CMD ["uvicorn", "lexrag.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
