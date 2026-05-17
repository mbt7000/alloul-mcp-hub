FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --no-dev
COPY src/ src/
EXPOSE 8009
CMD ["uv", "run", "python", "-m", "handex_workflow"]
