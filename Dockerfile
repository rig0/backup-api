FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api.py .
COPY modules/ modules/
COPY utils/ utils/

# Create directory for logs
RUN mkdir -p /app/logs

# Expose port
EXPOSE 7792

# Run the application
CMD ["python", "api.py"]
