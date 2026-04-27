# Running backend integration tests (Postgres)

This project includes integration tests for upload and schema that require a running Postgres database. These tests are gated and will be skipped when DATABASE_URL is not provided. You can run them locally or via Docker Compose (recommended).

## Using Docker Compose (recommended)

The repository provides a docker-compose stack used by CI which includes Postgres and the backend service. To run the integration tests locally with an ephemeral database:

1. Build and start the compose stack:

   docker compose up --build -d --wait

2. Run the integration tests inside the backend container:

   docker compose exec -T backend python -m unittest tests.test_document_upload

3. Tear down the stack when finished:

   docker compose down -v

Note: This mirrors the CI job in .github/workflows/ci.yml.

## Using an external Postgres instance

1. Create a Postgres database and obtain a DATABASE_URL, for example:

   export DATABASE_URL=postgresql://postgres:password@localhost:5432/maktaba_test
   export DATA_DIR=$(mktemp -d)

2. Initialize the test database and run the tests:

   python -m unittest tests.test_document_upload

## CI

The GitHub Actions workflow `.github/workflows/ci.yml` already includes a Compose-based job that builds the stack and runs the integration tests. If you need to run integration tests in a different CI environment, provide a Postgres service and set `DATABASE_URL` accordingly.
