<script lang="ts">
  import { onMount, tick } from 'svelte';
  import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
  import {
    PdfLoader,
    PdfHighlighter,
    HighlightsModel,
    type PdfHighlighterUtils,
  } from 'svelte-pdf-highlighter';
  import {
    backendToLibraryHighlight,
    buildCreatePayload,
    createHighlightClient,
    type BackendHighlight,
    type LibraryHighlight,
  } from './highlight-api';

  export let data: {
    apiUrl: string;
    fileUrl: string;
    document: {
      id: string;
      title?: string | null;
      authors?: string[];
      format?: string;
      created_at?: string;
      updated_at?: string;
      page_count?: number | null;
    };
    jobs: Array<{ status?: string; job_type?: string }>;
  };

  type ZoomMode = 'fit-width' | 'fit-page' | 'custom';
  type HighlightMode = 'text' | 'draw';
  type JobStatus = 'ready' | 'processing' | 'failed';

  type PopupHighlightLike = {
    id?: string;
    comment?: string | null;
    extracted_text?: string | null;
    content?: { text?: string };
  };

  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 3;
  const ZOOM_STEP = 0.1;
  const PDF_WORKER_SRC = pdfWorkerSrc;
  const DEFAULT_HIGHLIGHT_COLOR = '#fde047';
  const BLOCKING_JOB_TYPES = new Set(['extract_text', 'ocr']);

  let loading = true;
  let error: string | null = null;
  let statusMessage = 'Loading PDF…';
  let currentPage = 1;
  let totalPages = data.document.page_count ?? 0;
  let zoomMode: ZoomMode = 'fit-width';
  let highlightMode: HighlightMode = 'text';
  let customZoom = 1;
  let currentScale = 1;
  let pdfViewerHostEl: HTMLDivElement | null = null;
  let pdfScrollerEl: HTMLElement | null = null;
  let scrollFrame: number | null = null;
  let highlightsRefreshFrame: number | null = null;
  let initialZoomApplied = false;

  let highlights: BackendHighlight[] = [];
  const highlightsStore = new HighlightsModel<LibraryHighlight>([]);
  let unsubscribeHighlightsStore: (() => boolean) | null = null;
  let rebuildingHighlightsStore = false;
  let pendingHighlightIds = new Set<string>();
  let pendingDeleteIds = new Set<string>();
  const highlightClient = createHighlightClient(data.apiUrl, data.document.id);

  function promptDeleteHighlight(highlight: PopupHighlightLike) {
    if (!highlight.id) return;
    const text =
      highlight.extracted_text?.trim() ||
      highlight.comment?.trim() ||
      highlight.content?.text?.trim() ||
      '<no text>';
    const ok = confirm(`Highlight text:\n\n${text}\n\nDelete this highlight?`);
    if (ok) {
      void deleteHighlightById(highlight.id);
    }
  }

  let pdfHighlighterUtils: Partial<PdfHighlighterUtils> = {
    selectedTool: 'highlight_pen',
    selectedColorIndex: 0,
    colors: [DEFAULT_HIGHLIGHT_COLOR],
    highlightMixBlendMode: 'multiply',
    textSelectionDelay: -1,
  };

  $: documentTitle = data.document.title ?? 'Untitled';
  $: authorsLabel = data.document.authors && data.document.authors.length > 0
    ? data.document.authors.join(', ')
    : 'Unknown author';
  $: pageDisplay = totalPages > 0 ? `${currentPage} / ${totalPages}` : '—';
  $: zoomDisplay =
    zoomMode === 'fit-width'
      ? 'Fit width'
      : zoomMode === 'fit-page'
        ? 'Fit page'
        : `${Math.round((typeof pdfHighlighterUtils.currentScale === 'number' ? pdfHighlighterUtils.currentScale : customZoom) * 100)}%`;
  $: jobStatus = deriveJobStatus(data.jobs);
  $: jobStatusLabel =
    jobStatus === 'processing' ? 'Processing' : jobStatus === 'failed' ? 'Failed' : 'Ready';
  $: jobCountLabel = data.jobs.length === 1 ? '1 background job' : `${data.jobs.length} background jobs`;
  $: currentPageHighlights = highlights.filter((highlight) => highlight.page_number === currentPage);

  function clampZoom(value: number) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  }

  function deriveJobStatus(jobs: Array<{ status?: string; job_type?: string }> | undefined): JobStatus {
    const relevantJobs = (jobs || []).filter((job) => BLOCKING_JOB_TYPES.has(job.job_type || ''));
    if (relevantJobs.length === 0) return 'ready';
    const statuses = new Set(relevantJobs.map((job) => job.status));
    if (statuses.has('failed')) return 'failed';
    if ([...statuses].some((status) => status === 'pending' || status === 'processing')) {
      return 'processing';
    }
    return 'ready';
  }

  // Merge backend records into the existing store without dropping local (unpersisted) highlights.
  function syncHighlightsStore(records: BackendHighlight[] = highlights) {
    rebuildingHighlightsStore = true;
    const backendLibs = (records || []).map(backendToLibraryHighlight);
    const localPending = ((highlightsStore as any).highlights || []).filter((h: LibraryHighlight) => !h.serverPersisted);
    (highlightsStore as any).highlights = [...backendLibs, ...localPending];
    rebuildingHighlightsStore = false;
  }

  function subscribeToHighlightsStore() {
    unsubscribeHighlightsStore?.();
    unsubscribeHighlightsStore = highlightsStore.subscribe((storeHighlights) => {
      if (rebuildingHighlightsStore) return;

      for (const highlight of storeHighlights) {
        if (highlight.serverPersisted) continue;
        const highlightId = highlight.id ?? '';
        if (!highlightId || pendingHighlightIds.has(highlightId)) continue;
        void persistLibraryHighlight(highlight);
      }

      const storeIds = new Set(
        storeHighlights
          .map((highlight) => highlight.id)
          .filter((highlightId): highlightId is string => typeof highlightId === 'string' && highlightId.length > 0),
      );

      for (const persistedHighlight of highlights) {
        if (!storeIds.has(persistedHighlight.id) && !pendingDeleteIds.has(persistedHighlight.id)) {
          void deleteHighlightById(persistedHighlight.id, { suppressAlert: true });
        }
      }
    });
  }

  async function loadHighlights() {
    try {
      highlights = await highlightClient.fetchHighlights();
      syncHighlightsStore();
    } catch (e) {
      console.error('[highlight] Failed to load highlights', e);
    }
  }

  async function persistLibraryHighlight(highlight: LibraryHighlight) {
    const highlightId = highlight.id ?? '';
    const payload = buildCreatePayload(highlight);

    if (!payload) {
      highlightsStore.deleteHighlight(highlight);
      return;
    }

    pendingHighlightIds.add(highlightId);
    statusMessage = `Saving highlight on page ${payload.page_number}…`;

    try {
      const createdHighlight = await highlightClient.createHighlight(payload);
      highlights = [...highlights, createdHighlight];
      if (highlightId) {
        highlightsStore.editHighlight(highlightId, {
          id: createdHighlight.id,
          serverPersisted: true,
        } as Partial<LibraryHighlight>);
      }
      currentPage = createdHighlight.page_number;
      statusMessage = totalPages > 0
        ? `Showing page ${currentPage} of ${totalPages}`
        : `Saved highlight on page ${currentPage}`;
    } catch (e) {
      console.error('[highlight] create error', e);
      highlightsStore.deleteHighlight(highlight);
      alert('Unable to create highlight');
      statusMessage = 'Unable to create highlight';
    } finally {
      pendingHighlightIds.delete(highlightId);
    }
  }

  async function deleteHighlightById(id: string, options: { suppressAlert?: boolean } = {}) {
    pendingDeleteIds.add(id);
    try {
      await highlightClient.deleteHighlight(id);
      highlights = highlights.filter((highlight) => highlight.id !== id);
      const storeHighlight = highlightsStore.getHighlightById(id) as LibraryHighlight | undefined;
      if (storeHighlight) {
        highlightsStore.deleteHighlight(storeHighlight);
      }
      statusMessage = totalPages > 0
        ? `Showing page ${currentPage} of ${totalPages}`
        : 'Highlight deleted';
    } catch (e) {
      console.error(e);
      if (!options.suppressAlert) {
        alert('Unable to delete highlight');
      }
    } finally {
      pendingDeleteIds.delete(id);
    }
  }

  function preventContextMenu(event: MouseEvent) {
    event.preventDefault();
  }

  function disconnectPdfScroller() {
    if (pdfScrollerEl) {
      pdfScrollerEl.removeEventListener('scroll', handlePdfScroll);
    }
    pdfScrollerEl = null;
  }

  function updateCurrentPageFromScroll() {
    if (!pdfScrollerEl) return;

    const pages = Array.from(pdfScrollerEl.querySelectorAll<HTMLElement>('.page[data-page-number]'));
    if (pages.length === 0) return;

    const containerRect = pdfScrollerEl.getBoundingClientRect();
    const anchor = containerRect.top + Math.min(96, containerRect.height / 4);
    let bestPage = currentPage;
    let bestScore = Number.POSITIVE_INFINITY;

    for (const page of pages) {
      const pageNumber = Number(page.dataset.pageNumber || '0');
      if (!pageNumber) continue;
      const rect = page.getBoundingClientRect();
      const score = Math.abs(rect.top - anchor);
      if (score < bestScore) {
        bestScore = score;
        bestPage = pageNumber;
      }
    }

    if (bestPage !== currentPage) {
      currentPage = bestPage;
    }

    if (totalPages > 0) {
      statusMessage = `Showing page ${currentPage} of ${totalPages}`;
    }
  }

  function handlePdfScroll() {
    if (typeof window === 'undefined') return;
    if (scrollFrame !== null) {
      window.cancelAnimationFrame(scrollFrame);
    }
    scrollFrame = window.requestAnimationFrame(() => {
      scrollFrame = null;
      updateCurrentPageFromScroll();
    });
  }

  function ensurePdfScroller() {
    const nextScroller = pdfViewerHostEl?.querySelector<HTMLElement>('.PdfHighlighter') ?? null;
    if (nextScroller === pdfScrollerEl) return;
    disconnectPdfScroller();
    pdfScrollerEl = nextScroller;
    if (pdfScrollerEl) {
      pdfScrollerEl.addEventListener('scroll', handlePdfScroll, { passive: true });
      updateCurrentPageFromScroll();
    }
  }

  function syncPdfDocument(pdfDocument: { numPages: number }) {
    totalPages = pdfDocument.numPages;
    currentPage = Math.min(Math.max(currentPage, 1), totalPages || 1);
    loading = false;
    error = null;
    if (!initialZoomApplied) {
      statusMessage = `Loaded ${totalPages} pages`;
    }
    return totalPages;
  }

  function scheduleHighlightsRefresh() {
    if (typeof window === 'undefined') {
      syncHighlightsStore();
      return;
    }

    if (highlightsRefreshFrame !== null) {
      window.cancelAnimationFrame(highlightsRefreshFrame);
    }

    highlightsRefreshFrame = window.requestAnimationFrame(() => {
      highlightsRefreshFrame = window.requestAnimationFrame(() => {
        highlightsRefreshFrame = null;
        syncHighlightsStore();
        updateCurrentPageFromScroll();
      });
    });
  }

  function handleHighlighterRendered() {
    loading = false;
    error = null;
    void tick().then(() => {
      ensurePdfScroller();
      if (!initialZoomApplied) {
        initialZoomApplied = true;
        pdfHighlighterUtils.setCurrentScaleValue?.('page-width');
        zoomMode = 'fit-width';
      }
      scheduleHighlightsRefresh();
    });
  }

  function handlePdfLoadError(loadError: Error) {
    error = loadError.message;
    loading = false;
    statusMessage = 'Unable to open the PDF';
  }

  function setHighlightMode(mode: HighlightMode) {
    highlightMode = mode;
    pdfHighlighterUtils = {
      ...pdfHighlighterUtils,
      selectedTool: mode === 'text' ? 'highlight_pen' : 'area_selection',
      selectedColorIndex: 0,
      colors: [DEFAULT_HIGHLIGHT_COLOR],
      highlightMixBlendMode: 'multiply',
      textSelectionDelay: -1,
    };
    statusMessage = mode === 'text'
      ? 'Select text directly in the PDF to save a highlight.'
      : 'Click and drag over the PDF to draw a highlight box.';
  }

  function setFitWidth() {
    zoomMode = 'fit-width';
    statusMessage = 'Fitting to page width';
    pdfHighlighterUtils.setCurrentScaleValue?.('page-width');
    scheduleHighlightsRefresh();
  }

  function setFitPage() {
    zoomMode = 'fit-page';
    statusMessage = 'Fitting the full page';
    pdfHighlighterUtils.setCurrentScaleValue?.('page-fit');
    scheduleHighlightsRefresh();
  }

  function applyCustomZoom(nextZoom: number) {
    customZoom = clampZoom(nextZoom);
    zoomMode = 'custom';
    currentScale = customZoom;
    statusMessage = `Zoom set to ${Math.round(customZoom * 100)}%`;
    pdfHighlighterUtils.setCurrentScaleValue?.(customZoom);
    scheduleHighlightsRefresh();
  }

  function zoomIn() {
    applyCustomZoom((zoomMode === 'custom' ? customZoom : currentScale) + ZOOM_STEP);
  }

  function zoomOut() {
    applyCustomZoom((zoomMode === 'custom' ? customZoom : currentScale) - ZOOM_STEP);
  }

  function handleZoomInput(event: Event) {
    const target = event.currentTarget as HTMLInputElement;
    applyCustomZoom(Number(target.value) / 100);
  }

  function scrollToPage(pageNumber: number) {
    if (!pdfScrollerEl) return;
    const clampedPage = Math.min(Math.max(pageNumber, 1), totalPages || pageNumber);
    const pageEl = pdfScrollerEl.querySelector<HTMLElement>(`.page[data-page-number="${clampedPage}"]`);
    if (!pageEl) return;
    currentPage = clampedPage;
    pageEl.scrollIntoView({ block: 'start', behavior: 'smooth' });
    if (totalPages > 0) {
      statusMessage = `Showing page ${currentPage} of ${totalPages}`;
    }
  }

  function goToPreviousPage() {
    if (currentPage <= 1) return;
    scrollToPage(currentPage - 1);
  }

  function goToNextPage() {
    if (currentPage >= totalPages) return;
    scrollToPage(currentPage + 1);
  }

  onMount(() => {
    subscribeToHighlightsStore();
    syncHighlightsStore();
    void loadHighlights();
    setHighlightMode('text');

    return () => {
      unsubscribeHighlightsStore?.();
      disconnectPdfScroller();
      if (typeof window !== 'undefined') {
        if (scrollFrame !== null) {
          window.cancelAnimationFrame(scrollFrame);
        }
        if (highlightsRefreshFrame !== null) {
          window.cancelAnimationFrame(highlightsRefreshFrame);
        }
      }
    };
  });
</script>

{#snippet highlightPopup(highlight: PopupHighlightLike, setPinned: (flag: boolean) => void)}
  <div class="Highlight__popup" style="display: flex; align-items: center; gap: 0.25rem;">
    {#if highlight.comment || highlight.content?.text || highlight.extracted_text}
      <div style="margin: 5px; max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
        {highlight.comment || highlight.content?.text || highlight.extracted_text}
      </div>
    {:else}
      <div style="margin: 5px; white-space: nowrap;">Comment has no Text</div>
    {/if}

    <button
      type="button"
      class="TipButton"
      aria-label="Edit highlight"
      on:click={() => setPinned(true)}
    >
      <div style="height: 1.1rem; width: 1.1rem;" class="icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"/></svg>
      </div>
    </button>

    <button
      type="button"
      class="TipButton"
      style="color: rgb(220 38 38);"
      aria-label="Delete highlight"
      on:click={() => promptDeleteHighlight(highlight)}
    >
      <div style="height: 1.1rem; width: 1.1rem;">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 11v6"/><path d="M14 11v6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
      </div>
    </button>
  </div>
{/snippet}

<svelte:head>
  <title>{documentTitle} — Maktaba Reader</title>
</svelte:head>

<main class="mx-auto min-h-screen max-w-7xl px-6 py-8">
  <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
    <div>
      <p class="text-sm uppercase tracking-[0.28em] text-cyan-300">PDF reader</p>
      <h1 class="mt-2 text-3xl font-semibold text-white">{documentTitle}</h1>
      <p class="mt-2 text-sm text-slate-400">{authorsLabel}</p>
    </div>

    <div class="flex items-center gap-3">
      <a
        href="/library"
        class="rounded-full border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-800"
      >
        Back to library
      </a>
      <a
        href={data.fileUrl}
        target="_blank"
        rel="noreferrer"
        class="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-300/15"
      >
        Open original PDF
      </a>
    </div>
  </div>

  <div class="grid gap-6 grid-cols-[17rem_minmax(0,1fr)]">
    <aside class="sticky top-6 h-[calc(100vh-3rem)] space-y-4 overflow-auto rounded-3xl border border-slate-700/80 bg-slate-950/70 p-5 shadow-2xl shadow-cyan-950/10">
      <section class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Status</p>
            <p class="mt-1 text-sm text-slate-200">{statusMessage}</p>
          </div>
          <span
            class={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${
              jobStatus === 'ready'
                ? 'bg-emerald-500/15 text-emerald-300'
                : jobStatus === 'processing'
                  ? 'bg-amber-500/15 text-amber-300'
                  : 'bg-rose-500/15 text-rose-300'
            }`}
          >
            {jobStatusLabel}
          </span>
        </div>
        <p class="text-xs text-slate-400">{jobCountLabel}</p>
      </section>

      <section class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Document</p>
        <dl class="space-y-3 text-sm text-slate-300">
          <div class="flex items-start justify-between gap-3 border-t border-slate-800 pt-3 first:border-t-0 first:pt-0">
            <dt class="text-slate-500">Format</dt>
            <dd class="text-right text-slate-100">{(data.document.format || 'pdf').toUpperCase()}</dd>
          </div>
          <div class="flex items-start justify-between gap-3 border-t border-slate-800 pt-3">
            <dt class="text-slate-500">Pages</dt>
            <dd class="text-right text-slate-100">{data.document.page_count ?? totalPages ?? '—'}</dd>
          </div>
          <div class="flex items-start justify-between gap-3 border-t border-slate-800 pt-3">
            <dt class="text-slate-500">Current page</dt>
            <dd class="text-right text-slate-100">{pageDisplay}</dd>
          </div>
          <div class="flex items-start justify-between gap-3 border-t border-slate-800 pt-3">
            <dt class="text-slate-500">Zoom</dt>
            <dd class="text-right text-slate-100">{zoomDisplay}</dd>
          </div>
        </dl>
      </section>

      <section class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Page navigation</p>
        <div class="flex items-center gap-2">
          <button
            class="flex-1 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2 text-sm text-slate-200 transition disabled:cursor-not-allowed disabled:opacity-40"
            disabled={currentPage <= 1}
            on:click={goToPreviousPage}
          >
            Previous
          </button>
          <div class="min-w-24 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-center text-sm text-slate-100">
            {pageDisplay}
          </div>
          <button
            class="flex-1 rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2 text-sm text-slate-200 transition disabled:cursor-not-allowed disabled:opacity-40"
            disabled={currentPage >= totalPages}
            on:click={goToNextPage}
          >
            Next
          </button>
        </div>
        <p class="text-xs text-slate-500">Pages scroll continuously. Previous/Next jumps to the nearest page boundary.</p>
      </section>

      <section class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div class="flex items-center justify-between gap-3">
          <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Highlights</p>
          <span class="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-400">
            {highlightMode === 'text' ? 'Text select' : 'Draw box'}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <button
            type="button"
            class={`rounded-lg px-3 py-2 text-sm transition ${
              highlightMode === 'text'
                ? 'bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-400/30'
                : 'border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-slate-500'
            }`}
            on:click={() => setHighlightMode('text')}
          >
            Select text
          </button>
          <button
            type="button"
            class={`rounded-lg px-3 py-2 text-sm transition ${
              highlightMode === 'draw'
                ? 'bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-400/30'
                : 'border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-slate-500'
            }`}
            on:click={() => setHighlightMode('draw')}
          >
            Draw box
          </button>
        </div>

        {#if highlightMode === 'text'}
          <p class="text-sm text-slate-400">Select text directly in the PDF to save a highlight.</p>
        {:else}
          <p class="text-sm text-slate-400">Click and drag over the PDF to draw a highlight box.</p>
        {/if}

        {#if currentPageHighlights.length === 0}
          <p class="text-xs text-slate-500">No highlights on this page.</p>
        {:else}
          <ul class="space-y-1.5">
            {#each currentPageHighlights as h, i (h.id ?? i)}
              <li class="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-2.5 py-1.5 text-xs text-slate-300">
                <span class="min-w-0 flex-1 truncate">{h.extracted_text || '(no text extracted)'}</span>
                <button
                  type="button"
                  class="shrink-0 text-slate-500 transition hover:text-rose-400"
                  aria-label="Delete highlight"
                  on:click={() => promptDeleteHighlight(h)}
                >✕</button>
              </li>
            {/each}
          </ul>
        {/if}
      </section>

      <section class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Zoom</p>
        <div class="grid grid-cols-2 gap-2">
          <button
            class={`rounded-lg px-3 py-2 text-sm transition ${
              zoomMode === 'fit-width'
                ? 'bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-400/30'
                : 'border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-slate-500'
            }`}
            on:click={setFitWidth}
          >
            Fit width
          </button>
          <button
            class={`rounded-lg px-3 py-2 text-sm transition ${
              zoomMode === 'fit-page'
                ? 'bg-cyan-500/20 text-cyan-100 ring-1 ring-cyan-400/30'
                : 'border border-slate-700 bg-slate-800/70 text-slate-200 hover:border-slate-500'
            }`}
            on:click={setFitPage}
          >
            Fit page
          </button>
        </div>

        <div class="flex items-center gap-2">
          <button
            class="rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2 text-lg leading-none text-slate-100 transition hover:border-slate-500"
            aria-label="Zoom out"
            on:click={zoomOut}
          >
            −
          </button>
          <input
            class="w-full accent-cyan-300"
            type="range"
            min={MIN_ZOOM * 100}
            max={MAX_ZOOM * 100}
            step="5"
            value={Math.round((zoomMode === 'custom' ? customZoom : currentScale) * 100)}
            on:input={handleZoomInput}
          />
          <button
            class="rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2 text-lg leading-none text-slate-100 transition hover:border-slate-500"
            aria-label="Zoom in"
            on:click={zoomIn}
          >
            +
          </button>
        </div>
      </section>
    </aside>

    <section class="rounded-3xl border border-slate-700/80 bg-slate-950/70 shadow-2xl shadow-cyan-950/10">
      <div class="flex items-center justify-between border-b border-slate-800 px-5 py-4 text-sm text-slate-400">
        <div>{documentTitle}</div>
        <div>{pageDisplay}</div>
      </div>

      <div class="p-4">
        <div bind:this={pdfViewerHostEl} class="reader-pdf-shell relative h-[72vh] overflow-hidden rounded-2xl bg-slate-900/60">
          {#if error}
            <div class="flex h-full items-center justify-center p-6">
              <div class="max-w-lg rounded-2xl border border-rose-700 bg-rose-950/40 p-6 text-sm text-rose-100">
                <p class="font-semibold">Unable to load the reader</p>
                <p class="mt-2">{error}</p>
              </div>
            </div>
          {:else}
            <PdfLoader document={data.fileUrl} onError={handlePdfLoadError} workerSrc={PDF_WORKER_SRC}>
              {#snippet beforeLoad(progress)}
                <div class="flex h-full items-center justify-center rounded-2xl border border-slate-800 bg-slate-900/70 px-6 py-5 text-sm text-slate-300">
                  Loading PDF… {progress.total ? Math.floor((progress.loaded / progress.total) * 100) : 0}%
                </div>
              {/snippet}

              {#snippet errorMessage(loadError)}
                <div class="flex h-full items-center justify-center p-6">
                  <div class="max-w-lg rounded-2xl border border-rose-700 bg-rose-950/40 p-6 text-sm text-rose-100">
                    <p class="font-semibold">Unable to load the reader</p>
                    <p class="mt-2">{loadError.message}</p>
                  </div>
                </div>
              {/snippet}

              {#snippet pdfHighlighterWrapper(pdfDocument)}
                {@const _ready = syncPdfDocument(pdfDocument)}
                <PdfHighlighter
                  pdfDocument={pdfDocument}
                  {highlightsStore}
                  bind:pdfHighlighterUtils={pdfHighlighterUtils}
                  onContextMenu={preventContextMenu}
                  highlightPopup={highlightPopup as any}
                  onHighlightsRendered={handleHighlighterRendered}
                  scaleOnResize={true}
                  style="width: 100%; height: 100%; background: rgb(15 23 42);"
                />
              {/snippet}
            </PdfLoader>
          {/if}
        </div>
      </div>
    </section>
  </div>
</main>

<style>
  :global(.reader-pdf-shell .PdfHighlighter) {
    background: rgb(15 23 42);
  }

  :global(.reader-pdf-shell .pdfViewer .page) {
    margin: 1rem auto;
    box-shadow: 0 20px 50px rgb(0 0 0 / 0.35);
  }
</style>
