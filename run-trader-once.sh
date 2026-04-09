#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p state
docker compose run --rm -v "$(pwd)/state:/app/state" trader
