FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY . .

# Install all dependencies including uvicorn (via pyproject.toml)
RUN pip install --no-cache-dir -e .

# Cloud Run injects PORT at runtime (default 8080); HF Spaces uses 7860
ENV PORT=8080

EXPOSE ${PORT}

# Shell form so $PORT is expanded at runtime by Cloud Run
CMD uvicorn server.app:app --host 0.0.0.0 --port $PORT
