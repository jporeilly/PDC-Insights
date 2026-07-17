FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-mcp.txt

COPY app ./app
COPY mcp_server ./mcp_server
COPY ui ./ui
COPY asgi.py .

EXPOSE 5002 8765
# Default command runs the web app. The MCP server is started by overriding
# the command (see the insights-mcp service in docker-compose.yml).
# Two uvicorn workers: I/O-bound (PDC + LLM calls), same pattern as the
# Glossary Generator.
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "5002", "--workers", "2"]
