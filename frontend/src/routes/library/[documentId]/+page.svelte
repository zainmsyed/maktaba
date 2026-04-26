<script lang="ts">
  import { onMount, tick } from 'svelte';

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
  type JobStatus = 'ready' | 'processing' | 'failed';

  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 3;
  const ZOOM_STEP = 0.1;

  let loading = true;
  let error: string | null = null;
  let statusMessage = 'Loading PDF…';
  let pdfDocument: any = null;
  let currentPage = 1;
  let totalPages = 0;
  let zoomMode: ZoomMode = 'fit-width';
  let customZoom = 1;
  let currentScale = 1;
  let stageEl: HTMLDivElement | null = null;
  let canvasEl: HTMLCanvasElement | null = null;
  let resizeObserver: ResizeObserver | null = null;
  let renderTask: any = null;
  let renderToken = 0;
  let stageSize = { width: 0, height: 0 };
  let loadingTask: any = null;

  // highlights and selection state
  let highlights: any[] = [];
  let selecting = false;
  let selStart = { x: 0, y: 0 };
  let selRect = { left: 0, top: 0, width: 0, height: 0 };

  async function loadHighlights() {
    try {
      const resp = await fetch(`${data.apiUrl}/api/documents/${data.document.id}/highlights`);
      if (!resp.ok) {
        console.error('Failed to load highlights', resp.status);
        return;
      }
      const payload = await resp.json();
      highlights = payload.highlights || [];
    } catch (e) {
      console.error('Failed to load highlights', e);
    }
  }

  function getHighlightStyle(h: any) {
    if (!canvasEl) return '';
    const cw = canvasEl.clientWidth || 0;
    const ch = canvasEl.clientHeight || 0;
    const left = Math.round((h.x || 0) * cw);
    const top = Math.round((h.y || 0) * ch);
    const width = Math.max(1, Math.round((h.width || 0) * cw));
    const height = Math.max(1, Math.round((h.height || 0) * ch));
    return `left: ${left}px; top: ${top}px; width: ${width}px; height: ${height}px;`;
  }

  async function createHighlight(payload: { page_number: number; x: number; y: number; width: number; height: number }) {
    try {
      const resp = await fetch(`${data.apiUrl}/api/documents/${data.document.id}/highlights`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`Failed to create highlight: ${resp.status} ${txt}`);
      }
      const json = await resp.json();
      // append highlight
      highlights = [...highlights, json.highlight];
    } catch (e) {
      console.error(e);
      alert('Unable to create highlight');
    }
  }

  async function deleteHighlightById(id: string) {
    try {
      const resp = await fetch(`${data.apiUrl}/api/highlights/${id}`, { method: 'DELETE' });
      if (!resp.ok) throw new Error(`Failed to delete: ${resp.status}`);
      highlights = highlights.filter((h) => h.id !== id);
    } catch (e) {
      console.error(e);
      alert('Unable to delete highlight');
    }
  }

  function onHighlightClick(h: any) {
    // show extracted text and ask for delete
    const ok = confirm(`Highlight text:\n\n${h.extracted_text || '<no text>'}\n\nDelete this highlight?`);
    if (ok) {
      void deleteHighlightById(h.id);
    }
  }

  let activePointerId: number | null = null;
  let overlayPointerTarget: HTMLElement | null = null;

  function globalPointerMove(event: PointerEvent) {
    if (!selecting) return;
    if (activePointerId !== null && event.pointerId !== activePointerId) return;
    let rect: DOMRect;
    if (canvasEl) {
      rect = canvasEl.getBoundingClientRect();
    } else if (overlayPointerTarget) {
      rect = overlayPointerTarget.getBoundingClientRect();
    } else {
      rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    }
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    const x = Math.min(selStart.x, offsetX);
    const y = Math.min(selStart.y, offsetY);
    const w = Math.abs(offsetX - selStart.x);
    const h = Math.abs(offsetY - selStart.y);
    selRect = { left: x, top: y, width: w, height: h };
  }

  function finalizeSelectionFromRect() {
    if (!canvasEl) return;
    const cw = canvasEl.clientWidth || 0;
    const ch = canvasEl.clientHeight || 0;
    if (cw <= 0 || ch <= 0) return;
    const nx = selRect.left / cw;
    const ny = selRect.top / ch;
    const nw = selRect.width / cw;
    const nh = selRect.height / ch;
    if (nw < 0.01 || nh < 0.01) {
      selRect = { left: 0, top: 0, width: 0, height: 0 };
      return;
    }
    void createHighlight({ page_number: currentPage, x: nx, y: ny, width: nw, height: nh });
    selRect = { left: 0, top: 0, width: 0, height: 0 };
  }

  function removeGlobalPointerListeners() {
    if (typeof window === 'undefined') return;
    window.removeEventListener('pointermove', globalPointerMove, true);
    window.removeEventListener('pointerup', globalPointerUp, true);
    window.removeEventListener('pointercancel', globalPointerCancel, true);
  }

  function globalPointerUp(event: PointerEvent) {
    if (activePointerId !== null && event.pointerId !== activePointerId) return;
    if (overlayPointerTarget && overlayPointerTarget.hasPointerCapture(event.pointerId)) {
      try { overlayPointerTarget.releasePointerCapture(event.pointerId); } catch {}
    }
    removeGlobalPointerListeners();
    activePointerId = null;
    overlayPointerTarget = null;
    if (!selecting) return;
    selecting = false;
    finalizeSelectionFromRect();
  }

  function globalPointerCancel(event: PointerEvent) {
    if (activePointerId !== null && event.pointerId !== activePointerId) return;
    removeGlobalPointerListeners();
    activePointerId = null;
    overlayPointerTarget = null;
    selecting = false;
    selRect = { left: 0, top: 0, width: 0, height: 0 };
  }

  function onOverlayPointerDown(event: PointerEvent) {
    if (!canvasEl || event.button !== 0) return;
    const target = event.currentTarget as HTMLElement;
    try {
      target.setPointerCapture(event.pointerId);
    } catch {
      // ignore pointer capture failures in environments that don't support it
    }
    activePointerId = event.pointerId;
    overlayPointerTarget = target;
    const rect = target.getBoundingClientRect();
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    selecting = true;
    selStart = { x: offsetX, y: offsetY };
    selRect = { left: offsetX, top: offsetY, width: 0, height: 0 };
    if (typeof window !== 'undefined') {
      window.addEventListener('pointermove', globalPointerMove, true);
      window.addEventListener('pointerup', globalPointerUp, true);
      window.addEventListener('pointercancel', globalPointerCancel, true);
    }
  }

  function onOverlayPointerMove(event: PointerEvent) {
    // keep compatibility: direct handler simply delegates to global handler logic
    globalPointerMove(event);
  }

  function onOverlayPointerUp(event: PointerEvent) {
    // delegate to the global handler
    globalPointerUp(event);
  }

  function onOverlayPointerCancel(event: PointerEvent) {
    globalPointerCancel(event);
  }

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
        : `${Math.round(customZoom * 100)}%`;
  $: jobStatus = deriveJobStatus(data.jobs);
  $: jobStatusLabel =
    jobStatus === 'processing' ? 'Processing' : jobStatus === 'failed' ? 'Failed' : 'Ready';
  $: jobCountLabel = data.jobs.length === 1 ? '1 background job' : `${data.jobs.length} background jobs`;

  const BLOCKING_JOB_TYPES = new Set(['extract_text', 'ocr']);

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

  function clampZoom(value: number) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  }

  function updateStageSize() {
    if (!stageEl) return;
    const rect = stageEl.getBoundingClientRect();
    stageSize = {
      width: rect.width,
      height: rect.height,
    };
  }

  function calculateScale(page: any) {
    const baseViewport = page.getViewport({ scale: 1 });
    if (zoomMode === 'custom') {
      return clampZoom(customZoom);
    }

    if (!stageSize.width || !stageSize.height) {
      return zoomMode === 'fit-page' ? 1 : 1;
    }

    const widthBudget = Math.max(stageSize.width - 48, 1);
    const heightBudget = Math.max(stageSize.height - 48, 1);
    const widthScale = widthBudget / baseViewport.width;

    if (zoomMode === 'fit-page') {
      const heightScale = heightBudget / baseViewport.height;
      return Math.max(0.1, Math.min(widthScale, heightScale));
    }

    return Math.max(0.1, widthScale);
  }

  async function renderCurrentPage() {
    if (!pdfDocument || !canvasEl) return;

    const pageNumber = Math.min(Math.max(currentPage, 1), totalPages || 1);
    currentPage = pageNumber;
    const pageToken = ++renderToken;

    try {
      const page = await pdfDocument.getPage(pageNumber);
      if (pageToken !== renderToken) return;

      const scale = calculateScale(page);
      currentScale = scale;
      const viewport = page.getViewport({ scale });
      const outputScale = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
      const context = canvasEl.getContext('2d');

      if (!context) {
        throw new Error('Unable to access the PDF canvas');
      }

      if (renderTask?.cancel) {
        try {
          renderTask.cancel();
        } catch {
          // ignored — cancelling a completed render can throw in some pdf.js versions
        }
      }

      canvasEl.width = Math.floor(viewport.width * outputScale);
      canvasEl.height = Math.floor(viewport.height * outputScale);
      canvasEl.style.width = `${Math.floor(viewport.width)}px`;
      canvasEl.style.height = `${Math.floor(viewport.height)}px`;

      statusMessage = `Rendering page ${pageNumber}…`;
      renderTask = page.render({
        canvasContext: context,
        viewport,
        transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
      });

      await renderTask.promise;
      if (pageToken !== renderToken) return;

      statusMessage = `Showing page ${pageNumber} of ${totalPages}`;
      error = null;
    } catch (err) {
      const name = err instanceof Error ? err.name : '';
      if (name === 'RenderingCancelledException') {
        return;
      }

      error = err instanceof Error ? err.message : String(err);
      statusMessage = 'Unable to render the PDF';
    }
  }

  function setFitWidth() {
    zoomMode = 'fit-width';
    statusMessage = 'Fitting to page width';
    void renderCurrentPage();
  }

  function setFitPage() {
    zoomMode = 'fit-page';
    statusMessage = 'Fitting the full page';
    void renderCurrentPage();
  }

  function applyCustomZoom(nextZoom: number) {
    customZoom = clampZoom(nextZoom);
    zoomMode = 'custom';
    statusMessage = `Zoom set to ${Math.round(customZoom * 100)}%`;
    void renderCurrentPage();
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

  function goToPreviousPage() {
    if (currentPage <= 1) return;
    currentPage -= 1;
    statusMessage = `Page ${currentPage} of ${totalPages}`;
    void renderCurrentPage();
  }

  function goToNextPage() {
    if (currentPage >= totalPages) return;
    currentPage += 1;
    statusMessage = `Page ${currentPage} of ${totalPages}`;
    void renderCurrentPage();
  }

  async function loadDocument() {
    try {
      const pdfjs = await import('pdfjs-dist/build/pdf.mjs');
      const workerUrl = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default;
      pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

      loadingTask = pdfjs.getDocument({ url: data.fileUrl });
      pdfDocument = await loadingTask.promise;
      totalPages = pdfDocument.numPages;
      currentPage = 1;
      loading = false;
      statusMessage = `Loaded ${totalPages} pages`;
      // Wait for Svelte to flush DOM updates so the canvas element is bound
      // before we attempt to render into it.
      await tick();
      updateStageSize();
      await renderCurrentPage();
      // load persisted highlights for this document
      void loadHighlights();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
      loading = false;
      statusMessage = 'Unable to open the PDF';
    }
  }

  onMount(() => {
    const attachObserver = () => {
      if (typeof ResizeObserver === 'undefined' || !stageEl) {
        return false;
      }

      resizeObserver = new ResizeObserver(() => {
        updateStageSize();
        if (pdfDocument && zoomMode !== 'custom') {
          void renderCurrentPage();
        }
      });
      resizeObserver.observe(stageEl);
      return true;
    };

    if (!attachObserver() && typeof window !== 'undefined') {
      const handleResize = () => {
        updateStageSize();
        if (pdfDocument && zoomMode !== 'custom') {
          void renderCurrentPage();
        }
      };
      window.addEventListener('resize', handleResize);
      handleResize();
      void loadDocument();

      return () => {
        window.removeEventListener('resize', handleResize);
        resizeObserver?.disconnect();
        renderTask?.cancel?.();
        loadingTask?.destroy?.();
        pdfDocument?.destroy?.();
      };
    }

    updateStageSize();
    void loadDocument();

    return () => {
      resizeObserver?.disconnect();
      renderTask?.cancel?.();
      loadingTask?.destroy?.();
      pdfDocument?.destroy?.();
    };
  });
</script>

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
      <aside class="space-y-4 rounded-3xl border border-slate-700/80 bg-slate-950/70 p-5 shadow-2xl shadow-cyan-950/10 sticky top-6 h-[calc(100vh-3rem)] overflow-auto">
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
        </section>

        <section class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
          <p class="text-xs uppercase tracking-[0.24em] text-slate-500">Highlights</p>
          <p class="text-sm text-slate-400">Click and drag over the PDF to create a highlight. Click an existing highlight to delete it.</p>

          {#if highlights.filter(h => h.page_number === currentPage).length === 0}
            <p class="text-xs text-slate-500">No highlights on this page.</p>
          {:else}
            <ul class="space-y-1.5">
              {#each highlights.filter(h => h.page_number === currentPage) as h (h.id)}
                <li class="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/60 px-2.5 py-1.5 text-xs text-slate-300">
                  <span class="min-w-0 flex-1 truncate">{h.extracted_text || '(no text extracted)'}</span>
                  <button
                    type="button"
                    class="shrink-0 text-slate-500 transition hover:text-rose-400"
                    aria-label="Delete highlight"
                    on:click={() => void deleteHighlightById(h.id)}
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
        <div
          bind:this={stageEl}
          class="flex min-h-[72vh] items-center justify-center overflow-auto p-6"
        >
          {#if error}
            <div class="rounded-2xl border border-rose-700 bg-rose-950/40 p-6 text-sm text-rose-100 max-w-lg">
              <p class="font-semibold">Unable to load the reader</p>
              <p class="mt-2">{error}</p>
            </div>
          {:else if loading}
            <div class="rounded-2xl border border-slate-800 bg-slate-900/70 px-6 py-5 text-sm text-slate-300">
              Loading PDF…
            </div>
          {:else}
            <div class="relative inline-block">
              <canvas
                bind:this={canvasEl}
                class="max-w-none rounded-lg bg-white shadow-2xl shadow-black/30"
              ></canvas>

              <!-- highlight overlay and selection layer -->
              <div
                role="presentation"
                class="absolute inset-0 z-20"
                on:pointerdown={onOverlayPointerDown}
                on:pointermove={onOverlayPointerMove}
                on:pointerup={onOverlayPointerUp}
                on:pointercancel={onOverlayPointerCancel}
                style="cursor: crosshair; touch-action: none; user-select: none;"
              >
                {#each highlights as h (h.id)}
                  {#if h.page_number === currentPage}
                    <button
                      type="button"
                      class="absolute rounded-sm bg-amber-400/30 border border-amber-400/40"
                      style={getHighlightStyle(h)}
                      aria-label={`Highlight on page ${h.page_number}`}
                      on:click={(e) => { e.stopPropagation(); onHighlightClick(h); }}
                    ></button>
                  {/if}
                {/each}

                {#if selecting}
                  <div
                    class="absolute rounded-sm bg-cyan-300/20 border border-cyan-300"
                    style={`left: ${selRect.left}px; top: ${selRect.top}px; width: ${selRect.width}px; height: ${selRect.height}px;`}
                  ></div>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </section>
    </div>
</main>
