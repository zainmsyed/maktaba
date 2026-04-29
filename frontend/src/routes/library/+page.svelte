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
      documents = (payload.documents || []).map((item: any) => ({ document: item.document ?? item, jobs: item.jobs ?? [] }));
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

  function statusLabel(entry: DocWithJobs) {
    if (entry.uploading) return 'Uploading…';
    if (entry.error) return 'Upload failed';
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 'Processing';
    if (status === 'failed') return 'Failed';
    return 'Ready';
  }

  function progressLabel(entry: DocWithJobs) {
    if (entry.uploading) return 'Uploading…';
    if (entry.error) return 'Upload failed';
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 'Extracting…';
    if (status === 'failed') return 'Needs attention';
    const pageCount = Number(entry.document?.page_count ?? 0);
    return pageCount > 0 ? `${pageCount} pages` : 'Open to read';
  }

  function statusTone(entry: DocWithJobs) {
    if (entry.uploading) return 'amber';
    if (entry.error) return 'rose';
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 'amber';
    if (status === 'failed') return 'rose';
    return 'emerald';
  }

  function progressWidth(entry: DocWithJobs) {
    if (entry.uploading) return 24;
    if (entry.error) return 14;
    const status = jobStatus(entry.jobs);
    if (status === 'processing') return 42;
    if (status === 'failed') return 18;
    const pageCount = Number(entry.document?.page_count ?? 0);
    if (pageCount > 0) {
      return Math.min(100, Math.max(36, pageCount * 8));
    }
    return entry.document?.format?.toLowerCase() === 'epub' ? 82 : 68;
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
            <article class="book-card">
              <div class={`book-cover ${coverClass(index)} ${statusTone(entry)}`}>
                <div class="cover-noise"></div>
                <span class="format-badge">{(entry.document.format || '').toUpperCase() || 'PDF'}</span>
                <span class="cover-title">{entry.document.title ?? 'Untitled'}</span>
              </div>

              <div class="book-card-body">
                <div class="book-card-head">
                  <h2 class="book-card-title">{entry.document.title ?? 'Untitled'}</h2>
                  <span class={`status-pill ${statusTone(entry)}`}>{statusLabel(entry)}</span>
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
                    <div class={`book-prog-fill ${statusTone(entry)}`} style={`width: ${progressWidth(entry)}%`}></div>
                  </div>
                  <span class="book-prog-label">{progressLabel(entry)}</span>
                </div>

                <div class="book-card-footer">
                  <span class="book-card-date">{humanFormatDate(entry.document.created_at ?? entry.document.createdAt)}</span>
                  {#if readerHref(entry.document)}
                    <a href={readerHref(entry.document)} class="book-open">Open</a>
                  {:else}
                    <span class="book-open disabled">PDF only</span>
                  {/if}
                </div>
              </div>
            </article>
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

  :global(body) {
    margin: 0;
    min-height: 100vh;
    color: #1a1814;
    background: linear-gradient(180deg, #f7f4ee 0%, #e8e5de 100%);
    font-family: 'Lora', Georgia, serif;
    color-scheme: light;
  }

  :global(a) {
    color: inherit;
    text-decoration: none;
  }

  .library-page {
    min-height: 100vh;
    padding: 0;
  }

  .library-shell {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
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
    padding: 30px clamp(18px, 3vw, 40px) 40px;
  }

  .library-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin: 0 auto 22px;
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
  }

  .book-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.08);
  }

  .book-cover {
    position: relative;
    aspect-ratio: 2 / 3;
    padding: 14px 12px;
    display: flex;
    align-items: flex-end;
    overflow: hidden;
    color: rgba(255, 255, 255, 0.92);
  }

  .cover-noise {
    position: absolute;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.08'/%3E%3C/svg%3E");
    opacity: 0.16;
    mix-blend-mode: screen;
  }

  .format-badge {
    position: absolute;
    top: 10px;
    right: 10px;
    padding: 3px 6px;
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 4px;
    font-family: var(--font-serif);
    font-size: 8px;
    letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.72);
  }

  .cover-title {
    position: relative;
    z-index: 1;
    font-size: 12px;
    line-height: 1.35;
    font-weight: 500;
  }

  .cover-1 { background: linear-gradient(145deg, #2c3e50, #1a252f); }
  .cover-2 { background: linear-gradient(145deg, #8b4513, #5c2d0a); }
  .cover-3 { background: linear-gradient(145deg, #1a3a2a, #0d1f16); }
  .cover-4 { background: linear-gradient(145deg, #2d1b4e, #1a0f2e); }

  .book-card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px 14px 16px;
  }

  .book-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
  }

  .book-card-title {
    margin: 0;
    font-size: 13px;
    line-height: 1.35;
    font-weight: 500;
    color: #1a1814;
  }

  .book-card-author {
    margin: 0;
    font-family: var(--font-serif);
    font-size: 10px;
    font-weight: 300;
    color: #8a8680;
  }

  .status-pill {
    flex-shrink: 0;
    padding: 5px 9px;
    border-radius: 999px;
    font-family: var(--font-serif);
    font-size: 9px;
    font-weight: 400;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
  }

  .status-pill.emerald {
    background: rgba(16, 185, 129, 0.12);
    color: #047857;
  }

  .status-pill.amber {
    background: rgba(245, 158, 11, 0.12);
    color: #92400e;
  }

  .status-pill.rose {
    background: rgba(244, 63, 94, 0.12);
    color: #be123c;
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
    background: linear-gradient(90deg, #b85c2e, #d99447);
  }

  .book-prog-fill.emerald {
    background: linear-gradient(90deg, #36b37e, #65d19c);
  }

  .book-prog-fill.amber {
    background: linear-gradient(90deg, #d97706, #f59e0b);
  }

  .book-prog-fill.rose {
    background: linear-gradient(90deg, #e11d48, #fb7185);
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
    justify-content: space-between;
    gap: 8px;
    margin-top: 2px;
  }

  .book-card-date {
    font-family: var(--font-serif);
    font-size: 9px;
    font-weight: 300;
    color: #8a8680;
  }

  .book-open {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 54px;
    padding: 6px 9px;
    border-radius: 999px;
    border: 1px solid rgba(184, 92, 46, 0.28);
    background: rgba(240, 230, 220, 0.55);
    color: #b85c2e;
    font-family: var(--font-serif);
    font-size: 9px;
    font-weight: 400;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    transition: transform 0.15s, background 0.15s, border-color 0.15s;
  }

  .book-open:hover {
    transform: translateY(-1px);
    background: rgba(240, 230, 220, 0.9);
    border-color: rgba(184, 92, 46, 0.4);
  }

  .book-open.disabled {
    border-color: rgba(26, 24, 20, 0.12);
    background: rgba(242, 240, 235, 0.72);
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
