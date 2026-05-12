FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying source so this layer is cached on rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (venv, data, pycache excluded via .dockerignore)
COPY . .

# SQLite and memory go to /tmp so they land in Cloud Run's writable ephemeral
# disk rather than the read-only image filesystem.
ENV TUTOR_DB_PATH=/tmp/tutor-data/tutor.db
ENV TUTOR_MEMORY_PATH=/tmp/tutor-memory

# /tmp is always writable in Cloud Run; no mkdir needed.
# Keep /app/data for local runs where env vars aren't set.
RUN mkdir -p /app/data

# Run as non-root for Cloud Run security best practice
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
