FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy requirements and install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

# Copy project source
COPY src/ ./src/
COPY .env .

# Set Python path
ENV PYTHONPATH=/app/src

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["python", "-m", "src.Testaiownik.Backend.run", "--production", "--host", "0.0.0.0", "--port", "8000"]