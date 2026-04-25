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

  function deriveJobStatus(jobs: Array<{ status?: string }> | undefined): JobStatus {
    if (!jobs || jobs.length === 0) return 'ready';
    const statuses = new Set(jobs.map((job) => job.status));
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

  {#if error}
    <div class="rounded-2xl border border-rose-700 bg-rose-950/40 p-6 text-sm text-rose-100">
      <p class="font-semibold">Unable to load the reader</p>
      <p class="mt-2">{error}</p>
    </div>
  {:else}
    <div class="grid gap-6 lg:grid-cols-[19rem_minmax(0,1fr)]">
      <aside class="space-y-4 rounded-3xl border border-slate-700/80 bg-slate-950/70 p-5 shadow-2xl shadow-cyan-950/10 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] lg:overflow-auto">
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
          {#if loading}
            <div class="rounded-2xl border border-slate-800 bg-slate-900/70 px-6 py-5 text-sm text-slate-300">
              Loading PDF…
            </div>
          {:else}
            <canvas
              bind:this={canvasEl}
              class="max-w-none rounded-lg bg-white shadow-2xl shadow-black/30"
            ></canvas>
          {/if}
        </div>
      </section>
    </div>
  {/if}
</main>
