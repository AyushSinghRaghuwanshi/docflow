FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docflow ./docflow
# Results summary shown on the Benchmarks page
COPY evals/results/dashboard.json ./evals/results/dashboard.json

# Everything that must survive a restart lives on the /data volume:
# the database, the uploaded originals and the MCP inbox.
ENV DOCFLOW_DB=/data/docflow.db \
    DOCFLOW_FILES=/data/files \
    DOCFLOW_INBOX=/data/inbox
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "docflow.api:app", "--host", "0.0.0.0", "--port", "8000"]
