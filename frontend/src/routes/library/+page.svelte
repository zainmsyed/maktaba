<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

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
  // removed global uploading flag; use per-item uploading state
  let pollTimer: number | null = null;

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

  const BLOCKING_JOB_TYPES = new Set(['extract_text', 'ocr']);

  function jobStatus(jobs: JobModel[] | undefined) {
    const relevantJobs = (jobs || []).filter((job: any) => BLOCKING_JOB_TYPES.has(job.job_type || ''));
    if (relevantJobs.length === 0) return 'ready';
    const statuses = new Set(relevantJobs.map((j: any) => j.status));
    if (statuses.has('failed')) return 'failed';
    if ([...statuses].some((s) => s === 'pending' || s === 'processing')) return 'processing';
    return 'ready';
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
    // last_opened: use reading_progress.last_opened or updated_at fallback
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
</script>

<svelte:head>
  <title>Library — Maktaba</title>
</svelte:head>

<main class="mx-auto max-w-6xl px-6 py-10">
  <div class="mb-6 flex items-center justify-between">
    <div>
      <h1 class="text-3xl font-semibold">Library</h1>
      <p class="mt-1 text-sm text-slate-400">Your uploaded documents</p>
    </div>

    <div class="flex items-center gap-3">
      <label class="relative inline-flex cursor-pointer items-center rounded-full border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200">
        <input type="file" accept=".pdf,.epub" class="sr-only" on:change={onFileChange} />
        <svg xmlns="http://www.w3.org/2000/svg" class="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12" />
        </svg>
        Upload
      </label>

      <div class="flex items-center gap-2">
        <label for="library-sort" class="text-sm text-slate-400">Sort</label>
        <select id="library-sort" bind:value={sortMode} class="rounded-md bg-slate-900/60 px-2 py-1 text-sm text-slate-200 border border-slate-700">
          <option value="last_opened">Last opened</option>
          <option value="date_added">Date added</option>
          <option value="title">Title</option>
        </select>
      </div>
    </div>
  </div>

  {#if loading}
    <div class="rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center text-slate-400">Loading library…</div>
  {:else}
    {#if error}
      <div class="rounded-lg border border-rose-700 bg-rose-900/30 p-4 text-sm text-rose-200">{error}</div>
    {:else}
      {#if documents.length === 0}
        <div class="rounded-lg border border-slate-700 bg-slate-900/50 p-6 text-center text-slate-400">No documents yet — upload a PDF or EPUB to get started.</div>
      {:else}
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {#each sortedDocuments as entry (entry.document.id ?? entry.localId)}
            <div class="rounded-lg border border-slate-700 bg-slate-950/60 p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <h2 class="text-sm font-semibold text-white line-clamp-2">{entry.document.title ?? 'Untitled'}</h2>
                  <div class="mt-2 text-xs text-slate-400">
                    {#if entry.document.authors && entry.document.authors.length > 0}
                      {entry.document.authors.join(', ')}
                    {:else}
                      Unknown author
                    {/if}
                  </div>
                </div>

                <div class="flex flex-col items-end gap-2">
                  <div class="text-xs text-slate-400">{(entry.document.format || '').toUpperCase()}</div>

                  {#if entry.uploading}
                    <span class="inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-300">Uploading…</span>
                  {:else if entry.error}
                    <span class="inline-flex items-center rounded-full bg-rose-500/10 px-2 py-0.5 text-xs font-medium text-rose-300">Upload failed</span>
                  {:else}
                    {#if jobStatus(entry.jobs) === 'processing'}
                      <span class="inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-300">Processing</span>
                    {:else if jobStatus(entry.jobs) === 'failed'}
                      <span class="inline-flex items-center rounded-full bg-rose-500/10 px-2 py-0.5 text-xs font-medium text-rose-300">Failed</span>
                    {:else}
                      <span class="inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-300">Ready</span>
                    {/if}
                  {/if}
                </div>
              </div>

              <div class="mt-3 flex items-center justify-between text-xs text-slate-400">
                <div>{humanFormatDate(entry.document.created_at ?? entry.document.createdAt)}</div>
                <div class="flex items-center gap-2">
                  {#if readerHref(entry.document)}
                    <a
                      href={readerHref(entry.document)}
                      class="rounded-md bg-cyan-500/15 px-2 py-1 text-xs text-cyan-100 ring-1 ring-cyan-400/30 transition hover:bg-cyan-500/25"
                    >
                      Open
                    </a>
                  {:else}
                    <span class="rounded-md bg-slate-800/50 px-2 py-1 text-xs text-slate-500">PDF only</span>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</main>
