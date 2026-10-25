FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY docflow ./docflow
ENV DOCFLOW_DB=/data/docflow.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "docflow.api:app", "--host", "0.0.0.0", "--port", "8000"]
