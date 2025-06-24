#!/bin/bash

# Taken from
# https://gist.github.com/kwmiebach/e42dc4a43d5a2a0f2c3fdc41620747ab
get_toml_value() {
    local file="$1"
    local section="$2"
    local key="$3"
    get_section() {
        local file="$1"
        local section="$2"
        sed -n "/^\[$section\]/,/^\[/p" "$file" | sed '$d'
    }
    get_section "$file" "$section" | grep "^$key " | cut -d "=" -f2- | tr -d ' "'
}  

# Extract the version from pyproject.toml
VERSION_CODE=$(get_toml_value "./pyproject.toml" "project" "version")
if [ -z "$VERSION_CODE" ]; then
  echo "Error: Unable to retrieve version from pyproject.toml."
  exit 1
fi

echo "Building Pidroid version $VERSION_CODE"

# Extract the git commit hash
GIT_COMMIT=$(git rev-parse --short HEAD)
if [ -z "$GIT_COMMIT" ]; then
  echo "Error: Unable to retrieve git commit hash."
  exit 1
fi

docker build . --file Dockerfile --build-arg GIT_COMMIT="$GIT_COMMIT" --tag pidroid
docker tag pidroid ghcr.io/justanyones/pidroid:latest
docker tag pidroid "ghcr.io/justanyones/pidroid:$GIT_COMMIT"
docker tag pidroid "ghcr.io/justanyones/pidroid:$VERSION_CODE"