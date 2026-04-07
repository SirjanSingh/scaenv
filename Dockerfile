FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY . .

# Install all dependencies including uvicorn (via pyproject.toml)
RUN pip install --no-cache-dir -e .

# HF Spaces sets PORT=7860 automatically; set it explicitly as default (D-17)
ENV PORT=7860

EXPOSE 7860

# Run the OpenEnv HTTP server via uvicorn (D-15)
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
