# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y git ffmpeg

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY pidroid/ pidroid/

COPY alembic/ alembic/
COPY alembic.ini alembic.ini

CMD ["python3", "-u", "pidroid/main.py"]
