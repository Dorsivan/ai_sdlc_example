FROM python:3.11-slim

RUN pip install --no-cache-dir prometheus-client

COPY prometheus-exporter.py /app/exporter.py

WORKDIR /app

CMD ["python3", "/app/exporter.py"]
