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
RUN uv sync 



# Set Python path to parent directory (contains Testaiownik modules)
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8501


# Run the application from Frontend directory
CMD ["uv","run","streamlit", "run", "Frontend/main.py", "--server.port=8501", "--server.address=0.0.0.0"]