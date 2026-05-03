FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying source so this layer is cached on rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (venv, data, pycache excluded via .dockerignore)
COPY . .

# SQLite database lives here; create the dir so the app can write on first run
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
