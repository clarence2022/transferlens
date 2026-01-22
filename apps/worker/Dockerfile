FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /app/models /var/log/transferlens

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Make scripts executable
RUN chmod +x scripts/*.sh 2>/dev/null || true

# Default command: show help
CMD ["python", "-m", "worker.cli", "--help"]
