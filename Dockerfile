# syntax=docker/dockerfile:1

# Obtain the base image to be used
FROM python:3.12.3-slim-bookworm

# Install the required packages
RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y ffmpeg
RUN apt-get install -y gcc

# Create Pidroid user account
#RUN groupadd -g 999 pidroid
#RUN useradd -r -u 999 -g pidroid pidroid

# Switch the workdir
WORKDIR /app

# Install the Python dependencies
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# Copy alembic configurations
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

# Acquire the Git commit hash
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

# Copy over the other files
COPY pidroid/ pidroid/

# Switch to Pidroid user
#USER pidroid

CMD ["python3", "-u", "pidroid/main.py"]
