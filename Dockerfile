#
# sensai
# File: Dockerfile
# Copyright (c) 2026 Léo Lacordaire
#

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app:/app/src \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 7860

CMD ["python", "src/webapp/app.py"]
