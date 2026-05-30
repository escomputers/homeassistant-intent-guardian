FROM python:3.12-slim

WORKDIR /opt/intentguard/addon

COPY . /opt/intentguard

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

ENV INTENTGUARD_DB_PATH=/data/intentguard.db
ENV PYTHONUNBUFFERED=1

RUN chmod +x /opt/intentguard/addon/run.sh

EXPOSE 8000

CMD ["./run.sh"]
