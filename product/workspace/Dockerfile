FROM python:3.11-slim
WORKDIR /app
RUN pip install fastmcp asyncpg pydantic pydantic-settings PyJWT structlog redis httpx anthropic openai passlib apscheduler stripe pymupdf python-docx pytesseract Pillow tiktoken 2>&1 | tail -2
COPY shared/ /app/shared/
COPY product/workspace/src/ /app/src/
ENV PYTHONPATH=/app/src:/app
EXPOSE 8006
CMD ["python", "-m", "alloul_workspace"]
