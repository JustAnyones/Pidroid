#!/bin/sh
docker build . --file Dockerfile --build-arg GIT_COMMIT="$(git rev-parse --short HEAD)" --tag pidroid
docker tag pidroid ghcr.io/justanyones/pidroid
