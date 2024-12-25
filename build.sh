#!/bin/sh
docker build . --file Dockerfile --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) --tag pidroid
