FROM python:3.12-slim

# Install ffmpeg + yt-dlp dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp (latest) and Flask
RUN pip install --no-cache-dir yt-dlp flask gunicorn

WORKDIR /app
COPY server.py .

# Railway sets PORT env var
ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:8080", "--timeout", "120", "--workers", "2"]
