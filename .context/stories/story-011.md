# Story 011: Generate embeddings and semantic search

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Generate embeddings for searchable content and return semantic search results from pgvector using Ollama embeddings.

## Verification
Run a semantic query that does not share exact keywords with a note and confirm the matching note still appears in results.

## Scope — files this story may touch
- Embedding generation for notes and searchable highlight text
- Background job hook for embedding creation
- pgvector similarity queries
- Semantic search mode in the backend

## Out of scope — do not touch
- Hybrid ranking
- AI answer synthesis
- Provider switching beyond Ollama embeddings

## Dependencies
- Story 002
- Story 006
- Story 008

---

## Checklist
- [ ] Add an embedding service using the PRD's Ollama model
- [ ] Persist embeddings for notes and highlights
- [ ] Create a semantic search query path over pgvector
- [ ] Connect embedding creation to background processing
- [ ] Return semantic search results in a consistent API shape

---

## Issues

---

## Completion Summary

