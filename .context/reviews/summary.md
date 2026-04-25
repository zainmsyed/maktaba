# Review Summary

**Last updated:** 2026-04-25T10:59:03Z

## Findings
- When adding schema/bootstrap logic, include at least one automated Postgres smoke test for tables, extensions, and indexes. | count: 2 | status: promoted | sources: review-20260424-204758.md, review-20260424-205443.md
- Do not run privileged database DDL during regular application startup; keep it in migrations or explicit bootstrap flows. | count: 1 | status: tracked | sources: review-20260424-210450.md | stories: story-002
- Do not run superuser / admin DDL (CREATE EXTENSION, cluster-wide setup) on regular application startup; perform these in a controlled admin/migration step. | count: 1 | status: tracked | sources: review-20260424-205443.md
- Fail closed on upload validation; parser failures should reject the file instead of silently downgrading to filename fallback. | count: 1 | status: tracked | sources: review-20260425-011052.md | stories: story-003
- Never delete a canonical storage path during rollback unless the current transaction created that file. | count: 1 | status: tracked | sources: review-20260425-011052.md | stories: story-003
- Schema/bootstrap stories should include at least one automated database smoke test for required extensions, tables, and critical indexes. | count: 1 | status: tracked | sources: review-20260424-210450.md | stories: story-002
- When a parent row owns child rows, encode the intended `ON DELETE` action in the database foreign key instead of relying on application cleanup. | count: 1 | status: tracked | sources: review-20260424-210450.md | stories: story-002
- When adding a new service scaffold, include at least one smoke test and CI job to validate build-and-run. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When adding remembered rules, use the `/remember` workflow so the memory sync process remains authoritative. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When building frontend Docker images, commit and use a package-manager lockfile to ensure reproducible builds. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When creating a local Python virtualenv inside a repo, add it to `.gitignore` and remove it from the index immediately to avoid committing bulky artifacts. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When generating lockfiles for containerized builds, generate the lock with the same Python minor version used in the containers (e.g., `uv lock --python X.Y`). | count: 1 | status: tracked | sources: review-20260424-171509.md
- When ownership semantics exist (parent → child rows), declare the FK delete action at the schema level (ondelete) rather than relying only on application cleanup. | count: 1 | status: tracked | sources: review-20260424-205443.md
- When syncing Python dependencies in a slim Docker image, ensure required OS-level build dependencies are installed or use a base image that provides them. | count: 1 | status: tracked | sources: review-20260424-171509.md
- When the data model depends on delete cascades, declare the delete policy in the foreign key definition rather than relying on application-side cleanup. | count: 1 | status: tracked | sources: review-20260424-204758.md
