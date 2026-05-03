<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { computeProgressPercent } from '../../lib/progress';

  export let data: App.PageData;

  const apiUrl = data.apiUrl.replace(/\/$/, '');

  type DocumentModel = any;
  type JobModel = any;
  interface DocWithJobs {
    document: DocumentModel;
    jobs: JobModel[];
    localId?: string;
    uploading?: boolean;
    error?: string;
    highlight_count?: number;
    note_count?: number;
  }

  let documents: DocWithJobs[] = [];
  let sortedDocuments: DocWithJobs[] = [];
  let loading = true;
  let error: string | null = null;
  type SortMode = 'last_opened' | 'date_added' | 'title';

  let sortMode: SortMode = 'date_added';
  let pollTimer: number | null = null;

  // Search state
  let searchQuery = '';
  let searchResults: Array<{
    id: string;
    source_type: 'highlight' | 'note';
    document_id: string;
    document_title: string | null;
    page_number: number | null;
    content: string;
    highlight_id: string | null;
  }> = [];
  let searchOpen = false;
  let searchLoading = false;
  let searchError: string | null = null;
  let searchTimer: number | null = null;

  function clearSearch() {
    searchQuery = '';
    searchResults = [];
    searchOpen = false;
    searchError = null;
    if (searchTimer !== null) {
      clearTimeout(searchTimer);
      searchTimer = null;
    }
  }

  async function runSearch() {
    const q = searchQuery.trim();
    if (!q) {
      searchResults = [];
      searchOpen = false;
      return;
    }
    searchLoading = true;
    searchError = null;
    try {
      const resp = await fetch(`${apiUrl}/api/search?q=${encodeURIComponent(q)}&limit=20`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const payload = await resp.json();
      searchResults = payload.results || [];
      searchOpen = true;
    } catch (e) {
      searchError = e instanceof Error ? e.message : String(e);
      searchResults = [];
    } finally {
      searchLoading = false;
    }
  }

  function debouncedSearch() {
    if (searchTimer !== null) clearTimeout(searchTimer);
    if (!searchQuery.trim()) {
      searchResults = [];
      searchOpen = false;
      return;
    }
    searchTimer = setTimeout(() => {
      searchTimer = null;
      void runSearch();
    }, 250) as unknown as number;
  }

  function handleResultClick(result: typeof searchResults[0]) {
    clearSearch();
    if (!result.document_id) return;
    // Navigate to reader; explicit search targets should override normal progress restoration.
    const url = new URL(`/library/${result.document_id}`, window.location.href);
    const highlightId = result.highlight_id || (result.source_type === 'highlight' ? result.id : null);
    if (highlightId) {
      url.searchParams.set('highlight', highlightId);
    } else if (result.page_number) {
      url.searchParams.set('page', String(result.page_number));
    }
    void goto(url.pathname + url.search);
  }

  function goToLastReading() {
    try {
      const id = localStorage.getItem('maktaba:lastDocumentId');
      if (id) {
        void goto('/library/' + id);
        return;
      }
    } catch {}
    void goto('/library/demo');
  }

  const BLOCKING_JOB_TYPES = new Set(['extract_text', 'ocr']);

  async function loadDocuments(options: { silent?: boolean } = {}) {
    const { silent = false } = options;
    if (!silent) {
      loading = true;
      error = null;
    }
    try {
      const resp = await fetch(`${apiUrl}/api/documents`);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const payload = await resp.json();
      documents = (payload.documents || []).map((item: any) => ({
        document: item.document ?? item,
        jobs: item.jobs ?? [],
        highlight_count: item.highlight_count ?? 0,
        note_count: item.note_count ?? 0,
      }));
    } catch (e) {
      if (!silent) {
        error = e instanceof Error ? e.message : String(e);
      } else {
        console.error('Failed to refresh library documents', e);
      }
    } finally {
      if (!silent) {
        loading = false;
      }
    }
  }

  onMount(() => {
    loadDocuments();
  });

  onDestroy(() => {
    if (pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  });

  function jobStatus(jobs: JobModel[] | undefined) {
    const relevantJobs = (jobs || []).filter((job: any) => BLOCKING_JOB_TYPES.has(job.job_type || ''));
    if (relevantJobs.length === 0) return 'ready';
    const statuses = new Set(relevantJobs.map((j: any) => j.status));
    if (statuses.has('failed')) return 'failed';
    if ([...statuses].some((s) => s === 'pending' || s === 'processing')) return 'processing';
    return 'ready';
  }

  function statusTone(entry: DocWithJobs) {
    if (entry.uploading) return 'amber';
    if (entry.error) return 'rose';
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 'amber';
    if (status === 'failed') return 'rose';
    return 'emerald';
  }

  function getStoredProgress(docId: string) {
    try {
      const raw = localStorage.getItem(`maktaba:progress:${docId}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        return {
          // Use the user's current position, not furthest reached page.
          page: Number(parsed.lastPage) || Number(parsed.page) || Number(parsed.maxPage) || 0,
          total: Number(parsed.total) || 1,
        };
      }
    } catch {}
    return { page: 0, total: 1 };
  }

  function readingProgressPercent(entry: DocWithJobs) {
    const total = Number(entry.document?.page_count ?? 0);
    const stored = getStoredProgress(entry.document?.id ?? '');
    const reachedPage = Math.max(0, Math.floor(Number(stored.page) || 0));
    return computeProgressPercent(reachedPage, total);
  }

  function progressLabel(entry: DocWithJobs) {
    if (entry.uploading) return 'Uploading…';
    if (entry.error) return 'Upload failed';
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 'Extracting…';
    if (status === 'failed') return 'Needs attention';
    const total = Number(entry.document?.page_count ?? 0);
    if (total <= 0) return 'Open to read';
    return `${readingProgressPercent(entry)}%`;
  }

  function progressWidth(entry: DocWithJobs) {
    if (entry.uploading) return 24;
    if (entry.error) return 14;
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 42;
    if (status === 'failed') return 18;
    return readingProgressPercent(entry);
  }

  function progressComplete(entry: DocWithJobs) {
    return readingProgressPercent(entry) >= 100;
  }

  function humanFormatDate(iso: string | undefined) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  function documentTitleKey(entry: DocWithJobs): string {
    return (entry.document?.title ?? '').toLowerCase();
  }

  function documentCreatedTimestamp(entry: DocWithJobs): number {
    const doc = entry.document || {};
    return Date.parse(doc.created_at ?? doc.createdAt ?? '') || 0;
  }

  function documentLastActivityTimestamp(entry: DocWithJobs): number {
    const doc = entry.document || {};
    const lastOpened = doc.reading_progress?.last_opened;
    return lastOpened
      ? Date.parse(lastOpened) || 0
      : Date.parse(doc.updated_at ?? doc.updatedAt ?? '') || 0;
  }

  const documentSortComparators: Record<SortMode, (a: DocWithJobs, b: DocWithJobs) => number> = {
    title: (a, b) => documentTitleKey(a).localeCompare(documentTitleKey(b)),
    date_added: (a, b) => documentCreatedTimestamp(b) - documentCreatedTimestamp(a),
    last_opened: (a, b) => documentLastActivityTimestamp(b) - documentLastActivityTimestamp(a),
  };

  function sortDocuments(a: DocWithJobs, b: DocWithJobs, mode: SortMode): number {
    return documentSortComparators[mode](a, b);
  }

  // derive a sorted array reactively so Svelte change detection is reliable
  $: sortedDocuments = [...documents].sort((a, b) => sortDocuments(a, b, sortMode));

  // trigger polling decisions whenever documents change
  $: {
    const hasProcessing = documents.some((d) => jobStatus(d.jobs) === 'processing');
    if (hasProcessing && pollTimer === null) {
      pollTimer = setInterval(() => {
        loadDocuments({ silent: true });
      }, 5000) as unknown as number;
    } else if (!hasProcessing && pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function onFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    await upload(file);
    input.value = '';
  }

  function generateLocalId(): string {
    return typeof crypto !== 'undefined' && (crypto as any).randomUUID
      ? (crypto as any).randomUUID()
      : Math.random().toString(36).slice(2);
  }

  function buildOptimisticEntry(file: File, localId: string): DocWithJobs {
    return {
      document: {
        title: file.name.replace(/\.[^.]+$/, ''),
        authors: [],
        format: file.name.split('.').pop(),
        created_at: new Date().toISOString(),
      },
      jobs: [],
      localId,
      uploading: true,
    };
  }

  function mergeUploadResponse(localId: string, payload: any) {
    const newEntry = { document: payload.document, jobs: payload.jobs };
    const idx = documents.findIndex((d) => d.localId === localId);
    if (idx !== -1) {
      documents = documents.map((d) => (d.localId === localId ? newEntry : d));
    } else {
      documents = [newEntry, ...documents];
    }
  }

  function markUploadError(localId: string, message: string) {
    const idx = documents.findIndex((d) => d.localId === localId);
    if (idx !== -1) {
      documents = documents.map((d) =>
        d.localId === localId ? { ...d, uploading: false, error: message } : d,
      );
    }
  }

  async function upload(file: File) {
    const localId = generateLocalId();
    documents = [buildOptimisticEntry(file, localId), ...documents];
    try {
      const fd = new FormData();
      fd.append('file', file, file.name);
      const res = await fetch(`${apiUrl}/api/documents`, {
        method: 'POST',
        body: fd,
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(payload.detail || payload.error || `HTTP ${res.status}`);
      }
      mergeUploadResponse(localId, payload);
    } catch (e) {
      markUploadError(localId, e instanceof Error ? e.message : String(e));
    }
  }

  function readerHref(doc: any) {
    if (!doc?.id || (doc.format ?? '').toLowerCase() !== 'pdf') {
      return null;
    }
    return `/library/${doc.id}`;
  }

  function confirmDelete(title: string) {
    return confirm(`Delete "${title}"? This will remove the document and any associated highlights and notes.`);
  }

  function removeDocumentFromList(id: string) {
    documents = documents.filter((d) => (d.document?.id ?? d.localId) !== id);
  }

  // fallow-ignore-next-line complexity
  async function deleteDocument(entry: DocWithJobs) {
    const id = entry?.document?.id;
    if (!id) return;

    const title = entry.document?.title || 'Untitled';
    if (!confirmDelete(title)) return;

    try {
      const response = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
      const payload = response.ok ? await response.json() : null;
      if (!response.ok || !payload?.deleted) throw new Error(`HTTP ${response.status}`);
      removeDocumentFromList(id);
    } catch (e) {
      alert('Failed to delete document: ' + (e instanceof Error ? e.message : String(e)));
    }
  }
</script>

<svelte:head>
  <title>Library — Maktaba</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
</svelte:head>

<main class="library-page">
  <div class="library-shell">
    <header class="topbar">
      <div class="topbar-left">
        <span class="wordmark">maktaba</span>
        <nav class="nav-links" aria-label="Primary">
          <a class="nav-link active" href="/library">library</a>
          <a class="nav-link" href="/library/demo" on:click|preventDefault={goToLastReading}>reading</a>
        </nav>
      </div>

      <div class="search-wrap">
        <div class="search-box" class:search-box--active={searchOpen || searchQuery.length > 0}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="search-icon" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            type="search"
            class="search-input"
            placeholder="Search notes and highlights…"
            aria-label="Search notes and highlights"
            bind:value={searchQuery}
            on:input={debouncedSearch}
            on:keydown={(e) => { if (e.key === 'Escape') clearSearch(); }}
          />
          {#if searchLoading}
            <span class="search-spinner" aria-hidden="true">⟳</span>
          {/if}
        </div>
        {#if searchOpen}
          <div class="search-panel" role="listbox" aria-label="Search results">
            {#if searchError}
              <div class="search-error">{searchError}</div>
            {:else if searchResults.length === 0}
              <div class="search-empty">No results for “{searchQuery}”</div>
            {:else}
              {#each searchResults as result (result.id)}
                <button
                  type="button"
                  class="search-result"
                  role="option"
                  aria-selected="false"
                  on:click={() => handleResultClick(result)}
                >
                  <span class="search-result-type">{result.source_type}</span>
                  <span class="search-result-title">{result.document_title ?? 'Untitled'}</span>
                  {#if result.page_number}
                    <span class="search-result-page">{result.page_number}</span>
                  {/if}
                  <p class="search-result-snippet">{result.content}</p>
                </button>
              {/each}
            {/if}
          </div>
        {/if}
      </div>

    </header>

    <section class="library-view">
      <div class="library-toolbar">
        <p class="library-summary">{sortedDocuments.length} documents</p>

        <div class="library-header-actions">
          <label class="upload-btn paper-btn-accent">
            <input type="file" accept=".pdf,.epub" class="sr-only" on:change={onFileChange} />
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" x2="12" y1="3" y2="15"></line>
            </svg>
            Upload
          </label>

          <div class="sort-control">
            <label for="library-sort" class="sort-label">Sort</label>
            <select id="library-sort" bind:value={sortMode} class="sort-select">
              <option value="last_opened">Last opened</option>
              <option value="date_added">Date added</option>
              <option value="title">Title</option>
            </select>
          </div>
        </div>
      </div>

      {#if loading}
        <div class="library-state">Loading library…</div>
      {:else if error}
        <div class="library-state error">{error}</div>
      {:else if documents.length === 0}
        <div class="library-state">No documents yet - upload a PDF or EPUB to get started.</div>
      {:else}
        <div class="books-grid">
          {#each sortedDocuments as entry (entry.document.id ?? entry.localId)}
            {@const href = readerHref(entry.document)}
            <svelte:element this={href ? 'a' : 'article'} {href} class="book-card">
              <div class="book-card-body">
                <div class="book-card-head">
                  <h2 class="book-card-title">{entry.document.title ?? 'Untitled'}</h2>
                  {#if statusTone(entry) === 'emerald'}
                    <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="#047857" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  {:else if statusTone(entry) === 'amber'}
                    <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="#92400e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                  {:else if statusTone(entry) === 'rose'}
                    <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="#be123c" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  {/if}
                </div>
                <p class="book-card-author">
                  {#if entry.document.authors && entry.document.authors.length > 0}
                    {entry.document.authors.join(', ')}
                  {:else}
                    Unknown author
                  {/if}
                </p>
                <div class="book-progress-row">
                  <div class="book-prog-bar">
                    <div class="book-prog-fill" class:book-prog-fill--complete={progressComplete(entry)} style={`width: ${progressWidth(entry)}%`}></div>
                  </div>
                  <span class="book-prog-label">{progressLabel(entry)}</span>
                </div>
                <div class="book-card-footer">
                  <span class="book-card-date">{humanFormatDate(entry.document.created_at ?? entry.document.createdAt)}</span>
                </div>
                <div class="book-card-actions">
                  {#if entry.highlight_count || entry.note_count}
                    <div class="book-card-stats">
                      {#if entry.highlight_count}
                        <span class="book-stat" title="{entry.highlight_count} highlights">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11-6 6v3h9l3-3"/><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"/><path d="M15 3h6v6"/></svg>
                          {entry.highlight_count}
                        </span>
                      {/if}
                      {#if entry.note_count}
                        <span class="book-stat" title="{entry.note_count} notes">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                          {entry.note_count}
                        </span>
                      {/if}
                    </div>
                  {/if}

                  <button type="button" class="delete-btn push-right" on:click|preventDefault|stopPropagation={() => deleteDocument(entry)} title="Delete">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  </button>
                </div>
              </div>
            </svelte:element>
          {/each}
        </div>
      {/if}
    </section>
  </div>
</main>

<style>
  .library-page {
    min-height: 100vh;
    padding: 0;
    color: var(--ink);
    font-family: var(--font-serif);
    background: var(--app-bg);
  }

  .library-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: transparent;
  }

  .topbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(280px, 420px) minmax(0, 1fr);
    align-items: center;
    gap: 16px;
    padding: 14px 22px;
    background: var(--topbar-bg);
    border-bottom: 1px solid var(--rule);
    backdrop-filter: blur(8px);
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 18px;
    min-width: 0;
    justify-self: start;
  }

  .wordmark {
    font-size: 18px;
    font-weight: 500;
    letter-spacing: 0.07em;
    color: var(--ink);
  }

  .nav-links {
    display: flex;
    gap: 4px;
  }

  .nav-link {
    font-family: var(--font-serif);
    font-size: 14px;
    font-weight: 300;
    letter-spacing: 0.06em;
    color: var(--ink-3);
    padding: 5px 10px;
    border-radius: 5px;
    transition: background 0.15s, color 0.15s;
  }

  .nav-link:hover,
  .nav-link.active {
    color: var(--ink);
    background: var(--paper-2);
  }

  .library-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    flex-wrap: wrap;
  }

  .upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    text-transform: none;
  }

  .upload-btn:hover {
    transform: translateY(-1px);
  }

  .sort-control {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-serif);
  }

  .sort-label {
    font-size: 13px;
    font-weight: 300;
    color: var(--ink-3);
  }

  .sort-select {
    border: 1px solid var(--rule);
    border-radius: 8px;
    background: var(--panel-bg);
    color: var(--ink);
    padding: 7px 10px;
    font-size: 13px;
    font-weight: 300;
    font-family: var(--font-serif);
    outline: none;
  }

  .search-wrap {
    position: relative;
    width: 100%;
    max-width: 420px;
    min-width: 0;
    justify-self: center;
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 7px;
    border: 1px solid var(--rule);
    background: var(--panel-bg);
    transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
  }
  .search-box--active {
    border-color: color-mix(in srgb, var(--accent) 45%, var(--rule));
    background: var(--panel-bg-strong);
    box-shadow: var(--shadow-soft);
  }

  .search-icon {
    color: var(--ink-3);
    flex-shrink: 0;
  }

  .search-input {
    flex: 1;
    border: none;
    background: transparent;
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 400;
    color: var(--ink);
    outline: none;
    min-width: 0;
  }
  .search-input::placeholder {
    color: var(--ink-3);
  }

  .search-spinner {
    font-size: 14px;
    color: var(--ink-3);
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .search-panel {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    z-index: 50;
    background: var(--panel-bg-strong);
    border: 0.5px solid var(--rule);
    border-radius: 12px;
    box-shadow: var(--shadow-strong);
    max-height: 380px;
    overflow-y: auto;
    padding: 6px 0;
  }

  .search-empty,
  .search-error {
    padding: 14px 16px;
    font-family: var(--font-serif);
    font-size: 13px;
    color: var(--ink-3);
    text-align: center;
  }
  .search-error {
    color: #c44040;
  }

  .search-result {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 6px 10px;
    align-items: center;
    width: 100%;
    padding: 10px 14px;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.12s;
  }
  .search-result:hover {
    background: var(--paper-2);
  }

  .search-result-type {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 400;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ink-3);
    padding: 1px 6px;
    border-radius: 999px;
    background: var(--paper-2);
  }

  .search-result-title {
    font-family: var(--font-serif);
    font-size: 13px;
    font-weight: 500;
    color: var(--ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .search-result-page {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--ink-3);
    white-space: nowrap;
  }

  .search-result-snippet {
    grid-column: 1 / -1;
    margin: 0;
    font-family: var(--font-serif);
    font-size: 12px;
    font-weight: 300;
    color: var(--ink-2);
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .library-view {
    flex: 1;
    padding: 22px clamp(18px, 3vw, 40px) 30px;
  }

  .library-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin: 0 auto 16px;
    max-width: 1280px;
  }

  .library-summary {
    margin: 4px 0 0;
    font-family: var(--font-serif);
    font-size: 13px;
    font-weight: 300;
    letter-spacing: 0.08em;
    color: var(--ink-3);
  }

  .library-state {
    max-width: 1280px;
    margin: 0 auto;
    border: 1px solid var(--rule);
    border-radius: 18px;
    background: var(--panel-bg);
    padding: 26px 24px;
    text-align: center;
    color: var(--ink-2);
    box-shadow: var(--shadow-soft);
  }

  .library-state.error {
    border-color: rgba(196, 64, 64, 0.24);
    background: rgba(196, 64, 64, 0.08);
    color: #c44040;
  }

  .books-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 20px;
    max-width: 1280px;
    margin: 0 auto;
  }

  .book-card {
    display: flex;
    flex-direction: column;
    border-radius: 12px;
    overflow: hidden;
    background: var(--panel-bg-strong);
    border: 1px solid var(--rule);
    box-shadow: var(--shadow-soft);
    transition: transform 0.15s, box-shadow 0.15s;
    text-decoration: none;
    color: inherit;
    min-height: 168px;
  }

  .book-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-strong);
  }

  .book-card-body {
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 14px;
    flex: 1;
    justify-content: space-between;
  }

  .book-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }

  .book-card-title {
    margin: 0;
    font-size: 14px;
    line-height: 1.35;
    font-weight: 500;
    color: var(--ink);
    min-height: 2.4em;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .book-card-author {
    margin: 0;
    font-family: var(--font-serif);
    font-size: 14px;
    font-weight: 300;
    color: var(--ink-3);
  }

  .status-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }

  .delete-btn {
    background: transparent;
    border: none;
    padding: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    cursor: pointer;
    color: #c44040;
  }
  .delete-btn:hover {
    background: rgba(196,64,64,0.08);
  }

  .book-progress-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .book-prog-bar {
    flex: 1;
    height: 2px;
    border-radius: 999px;
    background: var(--paper-3);
    overflow: hidden;
  }

  .book-prog-fill {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #e11d48, #fb7185);
    transition: background 0.3s;
  }

  .book-prog-fill--complete {
    background: linear-gradient(90deg, #36b37e, #65d19c);
  }

  .book-prog-label {
    flex-shrink: 0;
    font-family: var(--font-serif);
    font-size: 12px;
    font-weight: 300;
    color: var(--ink-3);
    white-space: nowrap;
  }

  .book-card-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
  }

  .book-card-date {
    font-family: var(--font-serif);
    font-size: 12px;
    font-weight: 300;
    color: var(--ink-3);
  }

  .book-card-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-top: 2px;
  }

  .book-card-stats {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 2px;
  }

  .book-stat {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-family: var(--font-serif);
    font-size: 13px;
    font-weight: 400;
    color: var(--ink-3);
  }

  @media (max-width: 768px) {
    .topbar {
      flex-direction: column;
      align-items: stretch;
    }

    .topbar-left,
    .library-header-actions {
      flex-wrap: wrap;
      justify-content: space-between;
    }

    .topbar {
      grid-template-columns: 1fr;
    }

    .search-wrap {
      max-width: none;
    }

    .library-toolbar {
      flex-direction: column;
      align-items: flex-start;
    }

    .library-header-actions {
      justify-content: flex-start;
    }

    .books-grid {
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    }
  }
</style>
