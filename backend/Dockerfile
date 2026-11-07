FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy requirements first for caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --all-extras

# Copy application code
COPY munshi ./munshi
COPY sim ./sim
COPY eval ./eval
COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "fastapi", "dev", "munshi/main.py"]
