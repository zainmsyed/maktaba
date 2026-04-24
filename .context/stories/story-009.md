# Story 009: Surface background job status and retries

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Expose extraction and processing progress to the UI so uploads feel responsive and failed jobs can be retried.

## Verification
Upload a document and confirm the library status updates from processing to ready without a refresh; then force a failed job and confirm retry works.

## Scope — files this story may touch
- Jobs table state transitions
- Backend processing execution path
- SSE updates to the frontend
- UI status badges for processing and failure
- Manual reprocess action for failed jobs

## Out of scope — do not touch
- Search indexing status details
- Import job dashboards
- Analytics

## Dependencies
- Story 003
- Story 006
- Story 008

---

## Checklist
- [ ] Implement job status transitions for pending, processing, completed, and failed
- [ ] Add an SSE endpoint for job events
- [ ] Subscribe from the frontend and update document state live
- [ ] Show ready, processing, and failed states in the library
- [ ] Add a retry action for failed processing jobs

---

## Issues

---

## Completion Summary

