# Install uv
FROM python:3.12-slim@sha256:fa48eefe2146644c2308b909d6bb7651a768178f84fc9550dcd495e4d6d84d01 AS builder
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:5713fa8217f92b80223bc83aac7db36ec80a84437dbc0d04bbc659cae030d8c9 /uv /uvx /bin/

# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=/pidroid-bot/uv.lock,target=uv.lock \
    --mount=type=bind,source=/pidroid-bot/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy the project files into an intermediate image
COPY /pidroid-bot/pyproject.toml /pidroid-bot/uv.lock README.md /app/
COPY README.md /
COPY /pidroid-bot/src /app/src

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

FROM python:3.12-slim-bookworm

# Install libopus and ffmpeg
RUN apt-get update
RUN apt-get install libopus-dev -y --no-install-recommends
RUN rm -rf /var/lib/apt/lists/*
COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /usr/local/bin/

# Create Pidroid user account
RUN groupadd -g 999 pidroid
RUN useradd -r -u 999 -g pidroid pidroid

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Copy over alembic migration files
COPY /pidroid-bot/alembic/ /app/alembic/
COPY /pidroid-bot/alembic.ini /app/alembic.ini

ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

# Change the working directory to the `app` directory
WORKDIR /app

# Run the application
CMD ["/bin/sh", "-c", "/app/.venv/bin/migrate && /app/.venv/bin/bot"]
