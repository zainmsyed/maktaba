# Review Summary

**Last updated:** 2026-04-24T17:51:39Z

## Findings
- When adding a new service scaffold, include at least one smoke test and CI job to validate build-and-run. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When adding remembered rules, use the `/remember` workflow so the memory sync process remains authoritative. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When building frontend Docker images, commit and use a package-manager lockfile to ensure reproducible builds. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When creating a local Python virtualenv inside a repo, add it to `.gitignore` and remove it from the index immediately to avoid committing bulky artifacts. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When generating lockfiles for containerized builds, generate the lock with the same Python minor version used in the containers (e.g., `uv lock --python X.Y`). | count: 1 | status: tracked | sources: review-20260424-171509.md
- When syncing Python dependencies in a slim Docker image, ensure required OS-level build dependencies are installed or use a base image that provides them. | count: 1 | status: tracked | sources: review-20260424-171509.md
