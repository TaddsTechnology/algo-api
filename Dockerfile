FROM python:3.10-slim

# Install system dependencies including Firefox and tools
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    wget \
    gnupg \
    jq \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install geckodriver
RUN cd /tmp && \
    GECKO_VER="$(curl -s https://api.github.com/repos/mozilla/geckodriver/releases/latest | jq -r .tag_name)" && \
    wget "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VER}/geckodriver-${GECKO_VER}-linux64.tar.gz" && \
    tar -xzf geckodriver-*.tar.gz && \
    mv geckodriver /usr/local/bin/ && \
    chown root:root /usr/local/bin/geckodriver && \
    chmod 0755 /usr/local/bin/geckodriver

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/api/health || exit 1

# Start application with scheduled token refresh
CMD ["sh", "-c", "python scheduled_token_refresh.py & uvicorn streaming_api:app --host 0.0.0.0 --port 7860"]