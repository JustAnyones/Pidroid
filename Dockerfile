# syntax=docker/dockerfile:1

# Obtain the base image to be used
FROM alpine:20240606

# Install the required packages
RUN apk add bash python3=3.12.4-r0
RUN apk add gcc python3-dev musl-dev linux-headers
RUN apk add ffmpeg
RUN apk add poetry

# Create Pidroid user account
#RUN groupadd -g 999 pidroid
#RUN useradd -r -u 999 -g pidroid pidroid

# Switch the workdir
WORKDIR /app

# Move over poetry related files
COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
COPY README.md README.md

# Install dependencies early to cache them
RUN poetry install -E uvloop --no-root

# Copy alembic configurations
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

# Acquire the Git commit hash
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT

# Copy over the rest of the bot
COPY pidroid/ pidroid/

# Install the project again
RUN poetry install -E uvloop

# Switch to Pidroid user
#USER pidroid

CMD ["poetry", "run", "start"]
