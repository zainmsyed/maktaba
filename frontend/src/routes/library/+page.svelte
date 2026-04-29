<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';

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
  let sortMode: 'last_opened' | 'date_added' | 'title' = 'date_added';
  let pollTimer: number | null = null;

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
  const COVER_CLASSES = ['cover-1', 'cover-2', 'cover-3', 'cover-4'];

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
        return { page: Number(parsed.page) || 1, total: Number(parsed.total) || 1 };
      }
    } catch {}
    return { page: 0, total: 1 };
  }

  function progressLabel(entry: DocWithJobs) {
    if (entry.uploading) return 'Uploading…';
    if (entry.error) return 'Upload failed';
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 'Extracting…';
    if (status === 'failed') return 'Needs attention';
    const total = Number(entry.document?.page_count ?? 0);
    if (total <= 0) return 'Open to read';
    const stored = getStoredProgress(entry.document?.id ?? '');
    if (stored.page <= 0) return `${total} pages`;
    const pct = Math.min(100, Math.max(1, Math.round((stored.page / total) * 100)));
    return `${pct}%`;
  }

  function progressWidth(entry: DocWithJobs) {
    if (entry.uploading) return 24;
    if (entry.error) return 14;
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 42;
    if (status === 'failed') return 18;
    const total = Number(entry.document?.page_count ?? 0);
    if (total <= 0) return 0;
    const stored = getStoredProgress(entry.document?.id ?? '');
    if (stored.page <= 0) return 0;
    return Math.min(100, Math.max(1, Math.round((stored.page / total) * 100)));
  }

  function progressComplete(entry: DocWithJobs) {
    const total = Number(entry.document?.page_count ?? 0);
    if (total <= 0) return false;
    const stored = getStoredProgress(entry.document?.id ?? '');
    if (stored.page <= 0) return false;
    return stored.page >= total;
  }

  function humanFormatDate(iso: string | undefined) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  // derive a sorted array reactively so Svelte change detection is reliable
  $: sortedDocuments = [...documents].sort((a, b) => {
    const ad = a.document || {};
    const bd = b.document || {};
    if (sortMode === 'title') {
      const at = (ad.title ?? '').toLowerCase();
      const bt = (bd.title ?? '').toLowerCase();
      return at.localeCompare(bt);
    }
    if (sortMode === 'date_added') {
      const adt = Date.parse(ad.created_at ?? ad.createdAt ?? '') || 0;
      const bdt = Date.parse(bd.created_at ?? bd.createdAt ?? '') || 0;
      return bdt - adt;
    }
    const a_last = ad.reading_progress?.last_opened
      ? Date.parse(ad.reading_progress.last_opened)
      : Date.parse(ad.updated_at ?? ad.updatedAt ?? '') || 0;
    const b_last = bd.reading_progress?.last_opened
      ? Date.parse(bd.reading_progress.last_opened)
      : Date.parse(bd.updated_at ?? bd.updatedAt ?? '') || 0;
    return b_last - a_last;
  });

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

  async function upload(file: File) {
    const localId = typeof crypto !== 'undefined' && (crypto as any).randomUUID ? (crypto as any).randomUUID() : Math.random().toString(36).slice(2);
    const mockDoc = {
      title: file.name.replace(/\.[^.]+$/, ''),
      authors: [],
      format: file.name.split('.').pop(),
      created_at: new Date().toISOString(),
    };
    documents = [{ document: mockDoc, jobs: [], localId, uploading: true }, ...documents];
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
      const idx = documents.findIndex((d) => d.localId === localId);
      const newEntry = { document: payload.document, jobs: payload.jobs };
      if (idx !== -1) {
        documents = documents.map((d) => (d.localId === localId ? newEntry : d));
      } else {
        documents = [newEntry, ...documents];
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      const idx = documents.findIndex((d) => d.localId === localId);
      if (idx !== -1) {
        documents = documents.map((d) =>
          d.localId === localId ? { ...d, uploading: false, error: message } : d,
        );
      }
    }
  }

  function readerHref(doc: any) {
    if (!doc?.id || (doc.format ?? '').toLowerCase() !== 'pdf') {
      return null;
    }

    return `/library/${doc.id}`;
  }

  function coverClass(index: number) {
    return COVER_CLASSES[index % COVER_CLASSES.length];
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

      <div class="topbar-right">
        <label class="upload-btn">
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
    </header>

    <section class="library-view">
      <div class="library-header">
        <div>
          <p class="eyebrow">library</p>
          <h1 class="library-title">Your uploaded documents</h1>
        </div>
        <p class="library-summary">{sortedDocuments.length} documents</p>
      </div>

      {#if loading}
        <div class="library-state">Loading library…</div>
      {:else if error}
        <div class="library-state error">{error}</div>
      {:else if documents.length === 0}
        <div class="library-state">No documents yet - upload a PDF or EPUB to get started.</div>
      {:else}
        <div class="books-grid">
          {#each sortedDocuments as entry, index (entry.document.id ?? entry.localId)}
            {#if readerHref(entry.document)}
              <a href={readerHref(entry.document)} class="book-card">
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
                </div>
              </a>
            {:else}
              <article class="book-card">
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
                </div>
              </article>
            {/if}
          {/each}
        </div>
      {/if}
    </section>
  </div>
</main>

<style>
  :global(html) {
    min-height: 100%;
  }

  :global(a) {
    color: inherit;
    text-decoration: none;
  }

  .library-page {
    min-height: 100vh;
    padding: 0;
    color: #1a1814;
    font-family: 'Lora', Georgia, serif;
    color-scheme: light;
    background: linear-gradient(180deg, #f7f4ee 0%, #e8e5de 100%);
  }

  .library-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: linear-gradient(180deg, #f7f4ee 0%, #e8e5de 100%);
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 14px 22px;
    background: rgba(250, 248, 244, 0.94);
    border-bottom: 1px solid rgba(26, 24, 20, 0.08);
    backdrop-filter: blur(8px);
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 18px;
    min-width: 0;
  }

  .wordmark {
    font-size: 15px;
    font-weight: 500;
    letter-spacing: 0.07em;
    color: #1a1814;
  }

  .nav-links {
    display: flex;
    gap: 4px;
  }

  .nav-link {
    font-family: var(--font-serif);
    font-size: 11px;
    font-weight: 300;
    letter-spacing: 0.06em;
    color: #8a8680;
    padding: 5px 10px;
    border-radius: 5px;
    transition: background 0.15s, color 0.15s;
  }

  .nav-link:hover,
  .nav-link.active {
    color: #1a1814;
    background: rgba(242, 240, 235, 0.9);
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 14px;
    border-radius: 999px;
    border: 1px solid rgba(26, 24, 20, 0.14);
    background: rgba(242, 240, 235, 0.8);
    color: #1a1814;
    font-family: var(--font-serif);
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.06em;
    cursor: pointer;
    transition: transform 0.15s, background 0.15s, border-color 0.15s;
  }

  .upload-btn:hover {
    transform: translateY(-1px);
    background: #f0e6dc;
    border-color: rgba(26, 24, 20, 0.18);
  }

  .sort-control {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-serif);
  }

  .sort-label {
    font-size: 10px;
    font-weight: 300;
    color: #8a8680;
  }

  .sort-select {
    border: 1px solid rgba(26, 24, 20, 0.12);
    border-radius: 8px;
    background: rgba(250, 248, 244, 0.95);
    color: #1a1814;
    padding: 7px 10px;
    font-size: 10px;
    font-weight: 300;
    font-family: var(--font-serif);
    outline: none;
  }

  .library-view {
    flex: 1;
    padding: 22px clamp(18px, 3vw, 40px) 30px;
  }

  .library-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin: 0 auto 16px;
    max-width: 1280px;
  }

  .eyebrow {
    margin: 0 0 8px;
    font-family: var(--font-serif);
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #8a8680;
  }

  .library-title {
    margin: 0;
    font-size: 20px;
    font-weight: 500;
    color: #1a1814;
  }

  .library-summary {
    margin: 4px 0 0;
    font-family: var(--font-serif);
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.08em;
    color: #8a8680;
  }

  .library-state {
    max-width: 1280px;
    margin: 0 auto;
    border: 1px solid rgba(26, 24, 20, 0.08);
    border-radius: 18px;
    background: rgba(250, 248, 244, 0.88);
    padding: 26px 24px;
    text-align: center;
    color: #4a4640;
    box-shadow: 0 6px 28px rgba(0, 0, 0, 0.06);
  }

  .library-state.error {
    border-color: rgba(185, 28, 28, 0.2);
    background: rgba(254, 242, 242, 0.9);
    color: #991b1b;
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
    background: rgba(250, 248, 244, 0.95);
    border: 1px solid rgba(26, 24, 20, 0.08);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
    transition: transform 0.15s, box-shadow 0.15s;
    text-decoration: none;
    color: inherit;
    min-height: 168px;
  }

  .book-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.08);
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
    color: #1a1814;
    min-height: 2.4em;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .book-card-author {
    margin: 0;
    font-family: var(--font-serif);
    font-size: 11px;
    font-weight: 300;
    color: #8a8680;
  }

  .status-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
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
    background: rgba(232, 229, 222, 0.9);
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
    font-size: 9px;
    font-weight: 300;
    color: #8a8680;
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
    font-size: 9px;
    font-weight: 300;
    color: #8a8680;
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
    font-size: 10px;
    font-weight: 400;
    color: #8a8680;
  }

  @media (max-width: 768px) {
    .topbar {
      flex-direction: column;
      align-items: stretch;
    }

    .topbar-left,
    .topbar-right {
      flex-wrap: wrap;
      justify-content: space-between;
    }

    .library-header {
      flex-direction: column;
    }

    .books-grid {
      grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    }
  }
</style>
