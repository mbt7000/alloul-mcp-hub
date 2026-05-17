FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --no-dev
COPY src/ src/
EXPOSE 8004
CMD ["uv", "run", "python", "-m", "alloul_audit"]
