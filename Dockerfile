# syntax=docker/dockerfile:1

# Obtain the base image to be used
FROM python:3.12.4-slim-bookworm

# Install the required packages
RUN apt-get update -y
RUN apt-get upgrade -y
RUN apt-get install -y ffmpeg --no-install-recommends
RUN apt-get install -y python3-poetry

# Create Pidroid user account
#RUN groupadd -g 999 pidroid
#RUN useradd -r -u 999 -g pidroid pidroid

# Switch the workdir
WORKDIR /app

# Install the Python dependencies
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
RUN poetry env use /usr/local/bin/python3
RUN poetry install -E uvloop

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

CMD ["poetry", "run", "start"]
