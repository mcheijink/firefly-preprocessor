FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FIREFLY_WEB_DATA_DIR=/data
ENV APP_CONFIG_PATH=/data/config/config.yml

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /data/jobs /data/config

EXPOSE 8080

CMD ["uvicorn", "firefly_web.app:app", "--host", "0.0.0.0", "--port", "8080"]

