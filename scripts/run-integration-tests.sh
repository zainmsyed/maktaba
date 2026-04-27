#!/usr/bin/env bash
set -euo pipefail

# Helper to run the integration test suite locally via docker compose.
# Usage: ./scripts/run-integration-tests.sh

echo "Starting compose stack..."
docker compose up --build -d --wait

echo "Running backend integration tests..."
docker compose exec -T backend python -m unittest tests.test_document_upload

echo "Tearing down..."
docker compose down -v

echo "Integration tests finished."
