FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ara \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --no-dev
COPY src/ src/
EXPOSE 8008
CMD ["uv", "run", "python", "-m", "handex_docintel"]
