# Story 012: Merge hybrid search with temporal boosting

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Combine keyword and semantic search into a single ranked result set, with temporal boosting for recent or explicitly time-based queries.

## Verification
Search for a concept with a recent-date cue such as "recently" and confirm newer relevant notes rank above older ones.

## Scope — files this story may touch
- Weighted merge of keyword and semantic scores
- Temporal parsing for explicit recency signals
- Mild implicit recency bias for ties
- Frontend support for hybrid search mode

## Out of scope — do not touch
- AI-generated answers
- Related-notes surfacing
- Complex filter sidebars

## Dependencies
- Story 010
- Story 011

---

## Checklist
- [ ] Add score fusion for keyword and semantic result sets
- [ ] Add timestamp-aware temporal boosting to ranking
- [ ] Expose a hybrid search mode in the API
- [ ] Wire the UI to display hybrid results
- [ ] Validate that selected results still jump to the right location

---

## Issues

---

## Completion Summary

