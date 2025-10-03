FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make main.py executable
RUN chmod +x main.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TERM=xterm-256color

# Expose port for potential web UI (future)
EXPOSE 8080

# Default command - interactive mode
ENTRYPOINT ["python", "main.py"]
CMD ["--interactive"]
