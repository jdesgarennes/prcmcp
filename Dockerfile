FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 3000

CMD ["fastmcp", "run", "app/server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "3000", "--path", "/mcp/"]    