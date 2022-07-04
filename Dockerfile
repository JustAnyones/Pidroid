# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y git

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY pidroid/ pidroid/

CMD ["python3", "-u", "pidroid/main.py"]
