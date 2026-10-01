FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MCP_STATE_DIR=/data GEEKBI_AUTH_PATH=/data/geekbi-auth.json
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . \
    && useradd --uid 10001 --create-home mcp \
    && mkdir /data && chown mcp:mcp /data && chmod 700 /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["geekbi-temu-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
