FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY knowledge /app/knowledge
COPY content /app/content
COPY evals /app/evals
COPY web /app/web
RUN pip install --no-cache-dir .

ENV VERDICTPILOT_PROVIDER=offline
ENV VERDICTPILOT_EXECUTION_BACKEND=disabled
ENV VERDICTPILOT_PROJECT_ROOT=/app
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
EXPOSE 8000
CMD ["uvicorn", "verdictpilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
