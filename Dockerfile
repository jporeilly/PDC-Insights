FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-mcp.txt

COPY app ./app
COPY mcp_server ./mcp_server
COPY ui ./ui
COPY wsgi.py .

EXPOSE 8660 8765
# Default command runs the web app. The MCP server is started by overriding
# the command (see the insights-mcp service in docker-compose.yml).
# Threaded workers: I/O-bound (PDC + LLM calls), same pattern as the
# Glossary Generator.
CMD ["gunicorn", "--bind", "0.0.0.0:8660", "--workers", "2", \
     "--threads", "4", "--timeout", "180", "wsgi:app"]
