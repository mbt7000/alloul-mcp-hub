FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --no-dev
COPY src/ src/
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')"
EXPOSE 8003
CMD ["uv", "run", "python", "-m", "alloul_knowledge"]
