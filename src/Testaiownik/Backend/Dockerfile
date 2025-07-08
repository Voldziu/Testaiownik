FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy project files from root context
COPY pyproject.toml uv.lock* ./
COPY .env* ./

# Copy only the Testaiownik source code
COPY src/Testaiownik/ ./

# Install dependencies
RUN uv sync --frozen

# Set Python path to current directory
ENV PYTHONPATH=/app

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8000



# Run the application
CMD ["uv", "run", "python", "-m", "Backend.run", "--host", "0.0.0.0", "--port", "8000","--production"]