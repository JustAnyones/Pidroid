# syntax=docker/dockerfile:1

FROM python:3.12-bookworm AS builder

# Install Poetry
RUN pip install poetry==2.1.2

# Configure Poetry to use virtual environment in the project directory
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

# Copy over the dependencies
COPY pyproject.toml poetry.lock README.md ./

# And install those dependencies
RUN poetry install -E uvloop --without dev --no-root
RUN rm -rf $POETRY_CACHE_DIR


FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.source=https://github.com/JustAnyones/Pidroid
LABEL org.opencontainers.image.description="Pidroid Discord bot for TheoTown"
LABEL org.opencontainers.image.licenses=MIT

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install libopus and ffmpeg
RUN apt-get update
RUN apt-get install libopus-dev -y --no-install-recommends
RUN rm -rf /var/lib/apt/lists/*
COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /usr/local/bin/

# Create Pidroid user account
RUN groupadd -g 999 pidroid
RUN useradd -r -u 999 -g pidroid pidroid

# Copy dependencies from builder
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Copy over alembic migration files
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini

# Copy over the project files
COPY pidroid /app/pidroid
COPY pyproject.toml poetry.lock README.md /app/

# Set git commit
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

WORKDIR /app

# Install Pidroid package
RUN pip install .

# Perform migrations and run Pidroid
CMD alembic upgrade head && python -m pidroid.main
