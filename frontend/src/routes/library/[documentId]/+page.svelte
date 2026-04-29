<script lang="ts">
  import { browser } from '$app/environment';
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
    createNoteClient,
    type BackendHighlight,
    type BackendNote,
    type LibraryHighlight,
  } from './highlight-api';
  import NoteEditor from '../../../components/NoteEditor.svelte';
  import NotePopup from '../../../components/NotePopup.svelte';

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

  type NoteEditorTarget =
    | { kind: 'highlight'; highlight: BackendHighlight }
    | { kind: 'document' };

  type NoteGroup = {
    pageNumber: number;
    notes: BackendNote[];
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
  let unsubscribeHighlightsStore: (() => void) | null = null;
  let rebuildingHighlightsStore = false;
  let pendingHighlightIds = new Set<string>();
  let pendingDeleteIds = new Set<string>();
  const highlightClient = createHighlightClient(data.apiUrl, data.document.id);
  const noteClient = createNoteClient(data.apiUrl, data.document.id);

  let notes: BackendNote[] = [];
  let notesLoading = true;
  let notesError: string | null = null;
  let noteSidebarGroups: { documentNotes: BackendNote[]; pageGroups: NoteGroup[] } = {
    documentNotes: [],
    pageGroups: [],
  };
  let activeNoteTarget: NoteEditorTarget | null = null;
  let activeNoteRecord: BackendNote | null = null;
  let noteDraft = '';
  let noteSavedDraft = '';
  let noteStatusTone: 'muted' | 'saving' | 'saved' | 'error' = 'muted';
  let noteStatusText = 'Autosaves after 500ms';
  let noteAutosaveTimer: number | null = null;
  let noteSavedClearTimer: number | null = null;
  let noteEditorRevision = 0;
  let noteEditorPlacement: 'sidebar' | 'popup' | null = null;
  let noteTextareaEl: HTMLTextAreaElement | null = null;
  let noteEditorRef: any = null;

  async function saveFromEditor(draft: string) {
    const target = activeNoteTarget;
    if (!target) return null;
    const revision = noteEditorRevision;
    const note = activeNoteRecord;
    return await persistNoteDraft(target, note, draft, revision);
  }

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
  $: readingProgressLabel = totalPages > 0 ? `p. ${currentPage} of ${totalPages}` : 'p. —';
  $: readingProgressPercent = totalPages > 0 ? Math.max(1, Math.round((currentPage / totalPages) * 100)) : 0;
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
  $: noteSidebarGroups = groupNotesForSidebar(notes);

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

  function getNotePageNumber(note: BackendNote): number | null {
    return note.page_number ?? note.highlight?.page_number ?? null;
  }

  function compareNotes(a: BackendNote, b: BackendNote): number {
    const pageA = getNotePageNumber(a) ?? Number.POSITIVE_INFINITY;
    const pageB = getNotePageNumber(b) ?? Number.POSITIVE_INFINITY;
    if (pageA !== pageB) return pageA - pageB;

    const updatedA = Date.parse(a.updated_at || a.created_at || '') || 0;
    const updatedB = Date.parse(b.updated_at || b.created_at || '') || 0;
    if (updatedA !== updatedB) return updatedB - updatedA;

    return a.id.localeCompare(b.id);
  }

  function sortNotes(records: BackendNote[] = []) {
    return [...records].sort(compareNotes);
  }

  function groupNotesForSidebar(records: BackendNote[] = notes): { documentNotes: BackendNote[]; pageGroups: NoteGroup[] } {
    const documentNotes = sortNotes(records.filter((note) => getNotePageNumber(note) === null));
    const pageBuckets = new Map<number, BackendNote[]>();

    for (const note of records) {
      const pageNumber = getNotePageNumber(note);
      if (pageNumber === null) continue;
      const bucket = pageBuckets.get(pageNumber) ?? [];
      bucket.push(note);
      pageBuckets.set(pageNumber, bucket);
    }

    const pageGroups = [...pageBuckets.entries()]
      .sort(([pageA], [pageB]) => pageA - pageB)
      .map(([pageNumber, pageNotes]) => ({
        pageNumber,
        notes: sortNotes(pageNotes),
      }));

    return { documentNotes, pageGroups };
  }

  function getNotesForHighlight(highlightId: string | undefined | null) {
    if (!highlightId) return [];
    return sortNotes(notes.filter((note) => note.highlight_id === highlightId));
  }

  function getPrimaryNoteForHighlight(highlightId: string | undefined | null) {
    return getNotesForHighlight(highlightId)[0] ?? null;
  }

  function getHighlightById(highlightId: string | undefined | null) {
    if (!highlightId) return null;
    return highlights.find((highlight) => highlight.id === highlightId) ?? null;
  }

  function isActiveHighlightEditor(highlightId: string) {
    return activeNoteTarget?.kind === 'highlight' && Boolean(highlightId);
  }

  function noteIdleMessage(target: NoteEditorTarget | null = activeNoteTarget) {
    return target?.kind === 'highlight'
      ? 'Start typing to autosave this highlight note.'
      : 'Start typing to autosave this document note.';
  }

  function clearNoteTimers() {
    if (noteAutosaveTimer !== null) {
      window.clearTimeout(noteAutosaveTimer);
      noteAutosaveTimer = null;
    }
    if (noteSavedClearTimer !== null) {
      window.clearTimeout(noteSavedClearTimer);
      noteSavedClearTimer = null;
    }
  }

  function setNoteStatus(tone: typeof noteStatusTone, text: string) {
    noteStatusTone = tone;
    noteStatusText = text;
  }

  function resetNoteStatus(target: NoteEditorTarget | null = activeNoteTarget) {
    setNoteStatus('muted', noteIdleMessage(target));
  }

  function scheduleSavedNoteFade(revision: number, target: NoteEditorTarget | null) {
    if (noteSavedClearTimer !== null) {
      window.clearTimeout(noteSavedClearTimer);
    }
    noteSavedClearTimer = window.setTimeout(() => {
      noteSavedClearTimer = null;
      if (revision !== noteEditorRevision) return;
      if (noteDraft !== noteSavedDraft) return;
      resetNoteStatus(target);
    }, 2000);
  }

  function upsertNote(nextNote: BackendNote) {
    notes = sortNotes([...notes.filter((note) => note.id !== nextNote.id), nextNote]);
  }

  async function loadNotes() {
    notesLoading = true;
    notesError = null;
    try {
      notes = sortNotes(await noteClient.fetchNotes());
      if (activeNoteTarget === null) {
        resetNoteStatus(null);
      }
    } catch (e) {
      console.error('[note] Failed to load notes', e);
      notesError = e instanceof Error ? e.message : String(e);
    } finally {
      notesLoading = false;
    }
  }

  async function persistNoteDraft(
    target: NoteEditorTarget,
    note: BackendNote | null,
    draft: string,
    revision: number,
  ) {
    const isBlankNewNote = note === null && draft.trim().length === 0;
    if (isBlankNewNote) {
      if (revision === noteEditorRevision) {
        resetNoteStatus(target);
      }
      return null;
    }

    if (revision === noteEditorRevision) {
      setNoteStatus('saving', 'Saving…');
    }

    try {
      const savedNote = note
        ? await noteClient.updateNote(note.id, { content: draft })
        : await noteClient.createNote({
            content: draft,
            highlight_id: target.kind === 'highlight' ? target.highlight.id : null,
          });

      upsertNote(savedNote);

      if (revision === noteEditorRevision) {
        activeNoteRecord = savedNote;
        noteDraft = savedNote.content;
        noteSavedDraft = savedNote.content;
        setNoteStatus('saved', 'Saved');
        scheduleSavedNoteFade(revision, target);
      }

      return savedNote;
    } catch (e) {
      console.error('[note] Failed to save note', e);
      if (revision === noteEditorRevision) {
        setNoteStatus('error', 'Unable to save note');
      }
      return null;
    }
  }

  async function flushActiveNoteDraft() {
    const target = activeNoteTarget;
    if (!target) return;
    clearNoteTimers();

    // If the NoteEditor component exposes a programmatic save, use it to flush
    if (noteEditorRef && typeof noteEditorRef.save === 'function') {
      await noteEditorRef.save();
      return;
    }

    if (noteDraft === noteSavedDraft) return;
    const revision = noteEditorRevision;
    const note = activeNoteRecord;
    const draft = noteDraft;
    await persistNoteDraft(target, note, draft, revision);
  }

  async function openNoteEditor(target: NoteEditorTarget, note: BackendNote | null) {
    if (activeNoteTarget !== null) {
      await flushActiveNoteDraft();
    }

    noteEditorRevision += 1;
    activeNoteTarget = target;
    activeNoteRecord = note;
    noteDraft = note?.content ?? '';
    noteSavedDraft = noteDraft;
    clearNoteTimers();

    if (note) {
      setNoteStatus('saved', 'Saved');
      scheduleSavedNoteFade(noteEditorRevision, target);
    } else {
      resetNoteStatus(target);
    }

    void tick().then(() => {
      // focus the extracted NoteEditor component when available
      if (noteEditorRef?.focus) {
        noteEditorRef.focus();
      } else {
        noteTextareaEl?.focus();
        noteTextareaEl?.setSelectionRange?.(noteTextareaEl.value.length, noteTextareaEl.value.length);
      }
    });
  }

  async function openHighlightNoteEditor(
    highlightId: string,
    setPinned?: (flag: boolean) => void,
    placement: 'sidebar' | 'popup' = 'sidebar',
  ) {
    const highlight = getHighlightById(highlightId);
    if (!highlight) {
      console.warn(`[note] openHighlightNoteEditor: highlight ${highlightId} not found`);
      return;
    }
    noteEditorPlacement = placement;
    if (placement === 'popup') {
      setPinned?.(true);
    }
    await openNoteEditor({ kind: 'highlight', highlight }, getPrimaryNoteForHighlight(highlight.id));
  }

  async function openDocumentNoteEditor(note: BackendNote | null = null) {
    noteEditorPlacement = 'sidebar';
    await openNoteEditor({ kind: 'document' }, note);
  }

  function closeNoteEditor() {
    clearNoteTimers();
    noteEditorRevision += 1;
    activeNoteTarget = null;
    activeNoteRecord = null;
    noteDraft = '';
    noteSavedDraft = '';
    noteEditorPlacement = null;
    resetNoteStatus(null);
  }

  function handleNoteInput(event: Event) {
    const target = event.currentTarget as HTMLTextAreaElement;
    noteDraft = target.value;
    if (!activeNoteTarget) return;

    if (noteDraft === noteSavedDraft) {
      clearNoteTimers();
      resetNoteStatus(activeNoteTarget);
      return;
    }

    clearNoteTimers();
    setNoteStatus('saving', 'Saving…');
    const revision = noteEditorRevision;
    const note = activeNoteRecord;
    const draft = noteDraft;
    const source = activeNoteTarget;
    noteAutosaveTimer = window.setTimeout(() => {
      noteAutosaveTimer = null;
      void persistNoteDraft(source, note, draft, revision);
    }, 500);
  }

  async function handleSidebarNoteClick(note: BackendNote) {
    const pageNumber = getNotePageNumber(note);
    if (pageNumber === null) {
      void openDocumentNoteEditor(note);
      return;
    }

    scrollToPage(pageNumber);
    statusMessage = `Jumped to page ${pageNumber}`;

    // If this note is attached to a highlight, attempt to focus or open it.
    if (note.highlight_id) {
      // allow the PDF scroller and highlight DOM to settle
      await tick();

      let el: HTMLElement | null = null;

      // Prefer test selector (used in tests/mocks)
      el = pdfViewerHostEl?.querySelector(`[data-testid="mock-highlight-${note.highlight_id}"]`) as HTMLElement | null;

      // Then try a data attribute selector (used by some viewers)
      if (!el) {
        el = pdfViewerHostEl?.querySelector(`[data-highlight-id="${note.highlight_id}"]`) as HTMLElement | null;
      }

      // Fallback to getElementById (safer than `#id` in querySelector since ids may contain characters that need escaping)
      if (!el) {
        el = document.getElementById(String(note.highlight_id)) as HTMLElement | null;
      }

      // Final fallback: attribute selector for id (escape quotes if any)
      if (!el) {
        try {
          const escaped = String(note.highlight_id).replace(/"/g, '\\"');
          el = pdfViewerHostEl?.querySelector(`[id="${escaped}"]`) as HTMLElement | null;
        } catch (e) {
          // ignore selector construction errors
          el = null;
        }
      }

      if (el) {
        try {
          el.scrollIntoView?.({ block: 'start', behavior: 'smooth' } as any);
        } catch (e) {
          // ignore
        }

        const previousOutline = el.style.outline;
        const previousOutlineOffset = el.style.outlineOffset;
        const previousTabIndex = el.getAttribute('tabindex');
        if (previousTabIndex === null) {
          el.setAttribute('tabindex', '-1');
        }
        try {
          el.focus?.({ preventScroll: true } as any);
        } catch (e) {
          // ignore
        }
        el.style.outline = '2px solid rgb(34 211 238 / 0.9)';
        el.style.outlineOffset = '2px';
        window.setTimeout(() => {
          el.style.outline = previousOutline;
          el.style.outlineOffset = previousOutlineOffset;
          if (previousTabIndex === null) {
            el.removeAttribute('tabindex');
          }
        }, 1200);

        // Try to trigger the viewer's highlight activation (many viewers respond to click)
        try {
          el.click?.();
        } catch (e) {
          // ignore
        }

        // Attempt to open the inline note editor/popup as a fallback
        try {
          void openHighlightNoteEditor(note.highlight_id as string, undefined, 'popup');
        } catch (e) {
          // ignore
        }

        return;
      }
    }
  }

  async function handleNoteDelete(note: BackendNote) {
    if (!note || !note.id) return;
    const ok = confirm('Delete this note?');
    if (!ok) return;
    try {
      await noteClient.deleteNote(note.id);
      notes = notes.filter((n) => n.id !== note.id);
      if (activeNoteRecord?.id === note.id) {
        closeNoteEditor();
      }
      statusMessage = 'Note deleted';
    } catch (e) {
      console.error('[note] Failed to delete note', e);
      alert('Unable to delete note');
    }
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
      notes = notes.filter((note) => note.highlight_id !== id);
      if (activeNoteTarget?.kind === 'highlight' && activeNoteTarget.highlight.id === id) {
        closeNoteEditor();
      }
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
    if (typeof window !== 'undefined') {
      window.scrollTo(0, 0);
      history.scrollRestoration = 'manual';
      try {
        localStorage.setItem('maktaba:lastDocumentId', data.document.id);
      } catch {}
    }
    subscribeToHighlightsStore();
    syncHighlightsStore();
    void loadHighlights();
    void loadNotes();
    setHighlightMode('text');

    return () => {
      unsubscribeHighlightsStore?.();
      disconnectPdfScroller();
      clearNoteTimers();
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
  {@const highlightId = highlight.id ?? ''}
  {@const backendHighlight = getHighlightById(highlightId)}
  {@const highlightNote = getPrimaryNoteForHighlight(highlightId)}
  <div class="Highlight__popup hp-popup">
    <p class="hp-label">highlight</p>
    <p class="hp-text">
      {highlight.comment || highlight.content?.text || highlight.extracted_text || 'No text extracted'}
    </p>
    {#if highlightNote}
      <p class="hp-note-preview">{highlightNote.content || '(empty note)'}</p>
    {/if}
    <div class="hp-actions">
      <button
        type="button"
        class="hp-action-btn"
        aria-label={highlightNote ? 'Edit note' : 'Add note'}
        on:click={() => void openHighlightNoteEditor(highlightId, setPinned, 'popup')}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"/></svg>
        {highlightNote ? 'edit note' : 'add note'}
      </button>
      <button
        type="button"
        class="hp-action-btn hp-action-btn--danger"
        aria-label="Delete highlight"
        on:click={() => promptDeleteHighlight(highlight)}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 11v6"/><path d="M14 11v6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        delete
      </button>
    </div>
  </div>
{/snippet}

{#snippet editHighlightPopup(highlight: PopupHighlightLike)}
  {@const backendHighlight = getHighlightById(highlight.id ?? '')}
  {@const fallbackHighlight = {
    id: highlight.id ?? '',
    page_number: backendHighlight?.page_number ?? 1,
    extracted_text:
      backendHighlight?.extracted_text ??
      highlight.comment?.trim() ??
      highlight.content?.text?.trim() ??
      highlight.extracted_text?.trim() ??
      '',
  } as BackendHighlight}
  <NotePopup
    ariaLabel={getPrimaryNoteForHighlight(backendHighlight?.id ?? '') ? 'Edit highlight note' : 'Add highlight note'}
    title="highlight note"
    onClose={() => closeNoteEditor()}
  >
    <NoteEditor
      placement="popup"
      initialContent={getPrimaryNoteForHighlight(backendHighlight?.id)?.content ?? ''}
      highlight={backendHighlight ?? fallbackHighlight}
      onChange={(value) => { noteDraft = value; }}
      onSave={saveFromEditor}
      onClose={() => closeNoteEditor()}
      bind:this={noteEditorRef}
    />
  </NotePopup>
{/snippet}

<svelte:head>
  <title>{documentTitle} — Maktaba Reader</title>
  <style>
    :root {
      --paper-bg: #fcfbf8;
      --paper-bg-2: #e7dfd1;
      --paper-bg-3: #cfc4b1;
      --ink: #16130f;
      --ink-2: #2a241d;
      --ink-3: #5b544a;
      --accent: #a64f25;
      --accent-soft: #e2cfbd;
      --rule: rgba(22, 19, 15, 0.24);
    }

    html,
    body {
      height: 100%;
    }

    body {
      margin: 0;
      background: var(--paper-bg-3);
      color: var(--ink);
      color-scheme: light;
      font-family: 'Lora', Georgia, serif;
      overflow: hidden;
    }

    .maktaba-paper {
      min-height: 100vh;
      height: 100vh;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      background: var(--paper-bg);
      color: var(--ink);
      font-family: 'Lora', Georgia, serif;
      overflow: hidden;
    }

    .reader-topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      align-items: center;
      gap: 16px;
      height: 61px;
      box-sizing: border-box;
      padding: 14px 22px;
      background: rgba(250, 248, 244, 0.94);
      border-bottom: 1px solid rgba(26, 24, 20, 0.08);
      backdrop-filter: blur(8px);
    }

    .reader-topbar-left {
      display: flex;
      align-items: center;
      gap: 18px;
      min-width: 0;
      justify-self: start;
    }

    .reader-wordmark {
      font-family: var(--font-serif);
      font-size: 15px;
      font-weight: 500;
      letter-spacing: 0.07em;
      color: var(--ink);
      text-decoration: none;
    }

    .reader-nav { display: flex; gap: 4px; align-items: center; }

    .reader-nav-link {
      font-family: var(--font-serif);
      font-size: 11px;
      font-weight: 300;
      letter-spacing: 0.06em;
      color: var(--ink-3);
      padding: 5px 10px;
      border-radius: 5px;
      text-decoration: none;
      transition: background 0.15s, color 0.15s;
    }
    .reader-nav-link:hover, .reader-nav-link.active {
      color: var(--ink);
      background: rgba(242, 240, 235, 0.9);
    }

    .reader-topbar-center {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-width: 0;
      justify-self: center;
    }

    .reader-topbar-right {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 12px;
      min-width: 0;
      justify-self: end;
    }

    /* ── Topbar atoms ───────────────────── */
    .tb-label {
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 400;
      color: var(--ink-2);
      letter-spacing: 0.04em;
      white-space: nowrap;
    }
    .tb-progress-track { width: 68px; height: 2px; background: var(--paper-3); border-radius: 999px; overflow: hidden; }
    .tb-progress-fill  { height: 100%; background: var(--accent); border-radius: inherit; }

    .tb-status {
      font-family: var(--font-mono); font-size: 9px; font-weight: 400;
      letter-spacing: 0.08em; text-transform: uppercase;
      padding: 2px 8px; border-radius: 999px;
    }
    .tb-status--processing { background: rgba(245,158,11,.12); color: #92400e; }
    .tb-status--failed     { background: rgba(244,63,94,.12);  color: #be123c; }

    /* ── Dropdown menus ────────────────── */
    .tb-menu { position: relative; }

    .tb-summary {
      list-style: none;
      display: flex; align-items: center; gap: 5px;
      font-family: var(--font-serif); font-size: 10px; font-weight: 300;
      letter-spacing: 0.05em; color: var(--ink-3);
      padding: 5px 9px;
      border: 1px solid rgba(26, 24, 20, 0.12); border-radius: 8px;
      cursor: pointer; user-select: none;
      background: rgba(250, 248, 244, 0.95); white-space: nowrap;
      transition: background 0.15s, color 0.15s;
    }
    .tb-summary:hover { background: var(--paper-2); color: var(--ink); }
    .tb-summary::after { content: '\25BE'; font-size: 8px; margin-left: 2px; }
    .tb-summary::-webkit-details-marker { display: none; }

    .tb-dropdown {
      position: absolute; top: calc(100% + 4px); left: 0; z-index: 200;
      min-width: 150px;
      background: rgba(250,248,244,0.99);
      border: 0.5px solid rgba(26, 24, 20, 0.14);
      border-radius: 8px;
      box-shadow: 0 10px 30px rgba(0,0,0,.12), 0 2px 8px rgba(0,0,0,.08);
      backdrop-filter: none;
      padding: 4px 0;
    }
    .tb-dropdown--right { left: auto; right: 0; min-width: 180px; }

    .tb-dropdown-item {
      display: flex; align-items: center; width: 100%;
      padding: 8px 14px;
      font-family: var(--font-mono); font-size: 10px; font-weight: 300;
      letter-spacing: 0.05em; color: var(--ink);
      background: transparent; border: none; text-align: left;
      cursor: pointer; transition: background 0.12s;
    }
    .tb-dropdown-item:hover { background: var(--paper-2); }
    .tb-dropdown-item.tb-active { color: var(--ink); font-weight: 400; background: rgba(184,92,46,0.08); }
    .tb-dropdown-item.tb-active::before { content: '\2713  '; }

    .tb-dropdown-divider { height: 0.5px; background: var(--rule); margin: 4px 0; }

    .tb-slider-row { display: flex; align-items: center; gap: 8px; padding: 8px 14px; background: rgba(255,255,255,0.28); }
    .tb-slider-btn { font-size: 14px; color: var(--ink-3); background: transparent; border: none; cursor: pointer; padding: 0 2px; flex-shrink: 0; line-height: 1; }
    .tb-slider-btn:hover { color: var(--ink); }
    .tb-slider { flex: 1; accent-color: var(--accent); }

    /* ── Page navigation ──────────────── */
    .tb-nav { display: flex; align-items: center; border: 1px solid rgba(26, 24, 20, 0.12); border-radius: 8px; overflow: hidden; background: rgba(250, 248, 244, 0.95); }
    .tb-nav-btn {
      font-family: var(--font-mono); font-size: 13px; color: var(--ink-3);
      background: transparent; border: none; padding: 5px 9px; cursor: pointer;
      transition: background 0.12s, color 0.12s; line-height: 1;
    }
    .tb-nav-btn:first-child { border-right: 0.5px solid var(--rule); }
    .tb-nav-btn:last-child  { border-left:  0.5px solid var(--rule); }
    .tb-nav-btn:hover:not(:disabled) { background: var(--paper-2); color: var(--ink); }
    .tb-nav-btn:disabled { opacity: 0.3; cursor: default; }
    .tb-nav-page { padding: 5px 9px; }

    /* ── Link buttons ────────────────── */
    .tb-link {
      font-family: var(--font-serif); font-size: 10px; font-weight: 300;
      letter-spacing: 0.05em; color: var(--ink-3);
      text-decoration: none; padding: 5px 9px;
      border: 1px solid rgba(26, 24, 20, 0.12); border-radius: 8px;
      background: rgba(250, 248, 244, 0.95);
      white-space: nowrap; transition: background 0.15s, color 0.15s;
    }
    .tb-link:hover { background: var(--paper-2); color: var(--ink); }

    .sr-only {
      position: absolute; width: 1px; height: 1px;
      padding: 0; margin: -1px; overflow: hidden;
      clip: rect(0,0,0,0); border: 0;
    }

    /* ── Highlight popup ──────────────────────── */
    .hp-popup {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-width: 240px;
      max-width: 320px;
      background: var(--paper);
      border: 0.5px solid rgba(26,24,20,0.14);
      border-radius: 10px;
      box-shadow: 0 8px 28px rgba(0,0,0,.10), 0 2px 8px rgba(0,0,0,.07);
      padding: 14px 16px;
    }
    .hp-label {
      font-family: var(--font-mono);
      font-size: 9px;
      font-weight: 300;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--ink-3);
      margin: 0 0 6px;
    }
    .hp-text {
      font-family: var(--font-serif);
      font-size: 12px;
      line-height: 1.6;
      color: var(--ink);
      margin: 0 0 8px;
    }
    .hp-note-preview {
      font-family: var(--font-mono);
      font-size: 10.5px;
      font-weight: 300;
      color: var(--ink-2);
      border-left: 1.5px solid var(--accent-soft);
      padding-left: 8px;
      margin: 0 0 8px;
      line-height: 1.55;
    }
    .hp-actions {
      display: flex;
      gap: 8px;
    }
    .hp-action-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 300;
      letter-spacing: 0.05em;
      color: var(--ink-3);
      background: transparent;
      border: 0.5px solid var(--rule);
      border-radius: 5px;
      padding: 4px 9px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }
    .hp-action-btn:hover { background: var(--paper-2); color: var(--ink); }
    .hp-action-btn--danger:hover { background: rgba(244,63,94,.08); color: #be123c; border-color: rgba(244,63,94,.25); }

    .reader-workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      min-height: 0;
      height: 100%;
    }

    .reader-stage {
      order: 1;
      min-width: 0;
      height: 100%;
      display: flex;
      flex-direction: column;
      padding: 22px 32px 22px;
      background: var(--paper-bg);
    }

    .reader-meta {
      display: none;
    }

    .reader-kicker {
      margin: 0 0 10px;
      font-family: var(--font-serif);
      font-size: 10px;
      font-weight: 300;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--ink-3);
    }

    .reader-title {
      margin: 0;
      font-size: 19px;
      font-weight: 500;
      line-height: 1.3;
      color: var(--ink);
    }

    .reader-authors {
      margin: 12px 0 0;
      color: var(--ink-3);
      font-size: 13px;
    }

    .reader-stage-card {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--paper) !important;
      border-color: var(--rule) !important;
      box-shadow: 0 8px 48px rgba(0, 0, 0, 0.12), 0 1px 3px rgba(0, 0, 0, 0.08) !important;
    }

    .reader-stage-header {
      font-family: var(--font-serif);
      font-size: 14px;
      font-weight: 400;
      color: var(--ink-2) !important;
      background: rgba(252, 251, 248, 0.96);
      letter-spacing: 0.01em;
    }

    .reader-stage-header > div:last-child {
      font-variant-numeric: tabular-nums;
    }

    .reader-stage-body {
      flex: 1;
      min-height: 0;
      padding: 0;
      background: var(--paper);
    }

    .reader-sidebar {
      order: 2;
      position: relative !important;
      top: auto !important;
      height: 100% !important;
      font-family: var(--font-serif) !important;
      overflow: hidden !important;
      display: flex !important;
      flex-direction: column !important;
      gap: 0 !important;
      padding: 0 !important;
      border-radius: 0 !important;
      border: 0 !important;
      border-left: 1px solid var(--rule) !important;
      box-shadow: inset 1px 0 0 rgba(255, 255, 255, 0.35) !important;
      background: var(--paper-bg) !important;
    }

    .reader-sidebar-tabs {
      display: flex;
      padding: 0 18px;
      border-bottom: 1px solid var(--rule);
      background: rgba(252, 251, 248, 0.96);
      flex-shrink: 0;
    }

    .reader-sidebar-tab {
      padding: 14px 10px 12px;
      border-bottom: 1.5px solid transparent;
      font-family: var(--font-serif);
      font-size: 10px;
      font-weight: 400;
      letter-spacing: 0.09em;
      color: var(--ink-2);
      text-transform: lowercase;
    }

    .reader-sidebar-tab.active {
      color: var(--ink);
      border-bottom-color: var(--accent);
    }

    .reader-sidebar-search {
      padding: 10px 16px;
      border-bottom: 1px solid var(--rule);
      background: rgba(252, 251, 248, 0.96);
      flex-shrink: 0;
    }

    .reader-sidebar-search input {
      width: 100%;
      border: 1px solid rgba(22, 19, 15, 0.18);
      border-radius: 7px;
      padding: 7px 10px;
      background: rgba(255, 253, 249, 0.92);
      color: var(--ink);
      font-family: var(--font-serif);
      font-size: 11px;
      outline: none;
    }

    .reader-sidebar-search input::placeholder {
      color: var(--ink-3);
    }

    .reader-sidebar > section {
      margin: 0 !important;
      border: 0 !important;
      border-bottom: 1px solid var(--rule) !important;
      border-radius: 0 !important;
      background: rgba(252, 251, 248, 0.96) !important;
      box-shadow: none !important;
      padding: 14px 18px 16px !important;
    }

    .reader-highlights-panel .grid.grid-cols-2 button,
    .reader-navigation-panel button,
    .reader-stage .reader-topbar-actions a,
    .reader-sidebar .reader-sidebar-tab {
      font-family: var(--font-serif) !important;
      font-size: 10px !important;
      font-weight: 300 !important;
      letter-spacing: 0.08em !important;
    }

    .reader-highlights-panel .grid.grid-cols-2 button {
      min-height: 30px;
      border-radius: 0 !important;
      padding: 0 12px !important;
      background: var(--paper-bg-2) !important;
      border: 0.5px solid var(--rule) !important;
      color: var(--ink) !important;
      box-shadow: none !important;
    }

    .reader-highlights-panel .grid.grid-cols-2 button[class*='bg-cyan-500/20'] {
      background: var(--paper-bg) !important;
      border-color: var(--accent) !important;
      color: var(--ink) !important;
    }

    .reader-navigation-panel .flex.items-center.gap-2 > button,
    .reader-navigation-panel .min-w-24 {
      border-radius: 0 !important;
      background: var(--paper-bg) !important;
      border-color: var(--rule) !important;
      font-family: var(--font-serif) !important;
      font-size: 10px !important;
    }

    .reader-sidebar > section[data-testid='notes-sidebar'] {
      order: 1;
    }

    .reader-sidebar > section.reader-highlights-panel {
      order: 2;
    }

    .reader-sidebar > section.reader-status-panel {
      order: 3;
    }

    .reader-sidebar > section.reader-document-panel {
      order: 4;
    }

    .reader-sidebar > section.reader-navigation-panel {
      order: 5;
    }

    .reader-sidebar > section.reader-zoom-panel {
      order: 6;
      border-bottom: 0 !important;
    }

    .reader-sidebar .text-slate-500,
    .reader-sidebar .text-slate-400,
    .reader-sidebar .text-slate-300 {
      color: var(--ink-3) !important;
    }

    .reader-sidebar .text-slate-200,
    .reader-sidebar .text-slate-100,
    .reader-stage .text-slate-200,
    .reader-stage .text-slate-100 {
      color: var(--ink) !important;
    }

    .reader-sidebar p.text-xs.uppercase,
    .reader-sidebar p.text-[10px].uppercase {
      font-family: var(--font-serif);
      font-size: 10px !important;
      font-weight: 300;
      letter-spacing: 0.09em !important;
      color: var(--ink-3) !important;
      text-transform: lowercase;
    }

    .reader-sidebar button,
    .reader-sidebar select,
    .reader-sidebar textarea,
    .reader-sidebar input {
      font-family: var(--font-serif) !important;
    }

    .reader-sidebar button:not([aria-label='Delete highlight']):not([aria-label='Delete note']) {
      border-color: var(--rule) !important;
      background: var(--paper) !important;
      color: var(--ink) !important;
      box-shadow: none !important;
    }

    .reader-sidebar button[aria-label='Delete highlight'],
    .reader-sidebar button[aria-label='Delete note'] {
      color: var(--ink-3) !important;
    }

    .reader-sidebar [data-testid='notes-sidebar'] ul {
      gap: 0 !important;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li {
      padding: 0;
      border-bottom: 0.5px solid var(--rule);
    }

    .reader-sidebar [data-testid='notes-sidebar'] li:last-child {
      border-bottom: 0;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li > button:first-child {
      width: 100%;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
      padding: 14px 0 !important;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li > button:first-child:hover {
      background: transparent !important;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li > button:first-child p {
      border-left: 1.5px solid var(--paper-bg-3);
      padding-left: 9px;
      margin-top: 8px !important;
      color: var(--ink-2) !important;
      font-style: italic;
      font-family: 'Lora', Georgia, serif !important;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li > button:first-child span.text-sm {
      font-family: var(--font-serif);
      font-size: 11px !important;
      font-weight: 300;
      color: var(--ink) !important;
      white-space: normal;
      line-height: 1.65;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li > button:first-child .rounded-full {
      background: transparent !important;
      padding: 0 !important;
      font-family: var(--font-serif);
      font-size: 9px !important;
      font-weight: 300;
      letter-spacing: 0.08em;
      color: var(--ink-3) !important;
      text-transform: lowercase;
    }

    .reader-sidebar .reader-status-panel .inline-flex.rounded-full,
    .reader-sidebar .reader-document-panel .inline-flex.rounded-full,
    .reader-sidebar .reader-navigation-panel .inline-flex.rounded-full,
    .reader-sidebar .reader-zoom-panel .inline-flex.rounded-full {
      border-radius: 999px;
    }

    .reader-sidebar textarea,
    .reader-sidebar [aria-label='Note content'] {
      background: transparent !important;
      border: 0 !important;
      border-radius: 0 !important;
      padding: 0 !important;
      color: var(--ink) !important;
      box-shadow: none !important;
      resize: none;
    }

    .reader-sidebar [aria-label='Note content']::placeholder {
      color: var(--ink-3) !important;
    }

    .reader-sidebar .note-item,
    .reader-sidebar .note-item * {
      font-family: var(--font-serif) !important;
    }

    .reader-sidebar .rounded-2xl,
    .reader-stage .rounded-3xl {
      border-radius: 12px !important;
    }

    .reader-sidebar .border-slate-800,
    .reader-sidebar .border-slate-700,
    .reader-stage .border-slate-800,
    .reader-stage .border-slate-700 {
      border-color: var(--rule) !important;
    }

    .reader-sidebar .bg-slate-950\/70,
    .reader-sidebar .bg-slate-950\/60,
    .reader-sidebar .bg-slate-900\/70,
    .reader-sidebar .bg-slate-900\/60,
    .reader-sidebar .bg-slate-900\/80,
    .reader-sidebar .bg-slate-800\/70,
    .reader-stage .bg-slate-950\/70,
    .reader-stage .bg-slate-900\/60,
    .reader-stage .bg-slate-900\/70 {
      background: var(--paper) !important;
    }

    /* ── Sidebar paper sections ─────────────── */
    .reader-sidebar section {
      padding: 0;
      overflow-y: auto;
    }

    .reader-highlights-panel {
      border-bottom: 0.5px solid var(--rule);
      padding: 12px 18px;
      flex-shrink: 0;
    }

    .reader-notes-panel {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }

    .paper-notes-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 18px 8px;
      flex-shrink: 0;
    }

    .paper-sidebar-section-label {
      font-family: var(--font-mono);
      font-size: 9px;
      font-weight: 400;
      letter-spacing: 0.10em;
      text-transform: uppercase;
      color: var(--ink-2);
      margin: 0 0 8px;
    }

    .paper-notes-header .paper-sidebar-section-label {
      margin-bottom: 0;
    }

    .paper-sidebar-empty {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 400;
      color: var(--ink-2);
      margin: 0;
    }

    .paper-highlight-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }

    .paper-highlight-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 300;
      color: var(--ink-2);
      padding: 4px 0;
      border-bottom: 0.5px solid var(--rule);
    }
    .paper-highlight-item:last-child { border-bottom: 0; }
    .paper-highlight-item > span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .paper-hl-note-btn {
      font-family: var(--font-mono);
      font-size: 9px;
      font-weight: 300;
      letter-spacing: 0.08em;
      color: var(--accent);
      background: transparent;
      border: 0.5px solid var(--accent);
      border-radius: 4px;
      padding: 2px 6px;
      cursor: pointer;
      white-space: nowrap;
      flex-shrink: 0;
    }

    .paper-hl-del-btn {
      font-size: 9px;
      color: var(--ink-3);
      background: transparent;
      border: none;
      cursor: pointer;
      padding: 2px 4px;
      flex-shrink: 0;
    }
    .paper-hl-del-btn:hover { color: #c44040; }

    .paper-add-note-btn {
      font-size: 9px !important;
      padding: 4px 10px !important;
    }

    .paper-note-group-label {
      font-family: var(--font-mono);
      font-size: 9px;
      font-weight: 400;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--ink-2);
      padding: 12px 18px 6px;
      margin: 0;
    }

    .paper-note-item {
      border-bottom: 1px solid rgba(22, 19, 15, 0.10);
      border-top: 1px solid rgba(255, 255, 255, 0.6);
      padding: 12px 18px;
      background: rgba(255, 253, 249, 0.98);
      transition: background 0.12s;
    }
    .paper-note-item:hover { background: #ffffff; }

    .paper-note-loc {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 6px;
    }

    .paper-note-label {
      font-family: var(--font-mono);
      font-size: 9px;
      font-weight: 400;
      letter-spacing: 0.08em;
      color: var(--ink-2);
    }

    .paper-note-quote {
      font-size: 11px;
      font-style: italic;
      color: var(--ink-2);
      border-left: 2px solid var(--accent);
      padding-left: 8px;
      margin-bottom: 8px;
      line-height: 1.5;
    }

    .paper-note-body-row {
      display: flex;
      align-items: flex-start;
      gap: 6px;
    }

    .paper-note-body-btn {
      flex: 1;
      text-align: left;
      background: transparent;
      border: none;
      padding: 0;
      cursor: pointer;
      color: inherit;
    }

    .paper-note-body {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 400;
      line-height: 1.65;
      color: var(--ink);
    }

    .paper-note-del {
      font-size: 10px;
      color: var(--ink-3);
      background: transparent;
      border: none;
      cursor: pointer;
      padding: 2px 4px;
      flex-shrink: 0;
    }
    .paper-note-del:hover { color: #c44040; }

    .reader-sidebar .text-cyan-100,
    .reader-sidebar .text-amber-300,
    .reader-sidebar .text-emerald-300,
    .reader-sidebar .text-rose-300,
    .reader-topbar .text-cyan-100 {
      color: var(--ink) !important;
    }

    .reader-sidebar .ring-cyan-400\/30,
    .reader-sidebar .focus\:ring-cyan-400\/20 {
      box-shadow: none !important;
    }

    .reader-sidebar input[type='range'] {
      accent-color: var(--accent);
    }

    @media (max-width: 1100px) {
      .reader-workspace {
        grid-template-columns: minmax(0, 1fr);
      }

      .reader-sidebar {
        border-left: 0 !important;
        border-top: 0.5px solid var(--rule) !important;
      }

      .reader-stage {
        padding: 14px 16px;
      }

      .reader-stage-card {
        height: auto;
        min-height: 60vh;
      }

      .reader-topbar {
        flex-wrap: wrap;
        height: auto;
        padding: 8px 14px;
      }

      .reader-topbar-center {
        order: 3;
        width: 100%;
        justify-content: flex-start;
      }

      .reader-topbar-right {
        flex-wrap: wrap;
      }
    }
  </style>
</svelte:head>

<main class="reader-shell maktaba-paper">
  <header class="reader-topbar">
    <div class="reader-topbar-left">
      <a href="/library" class="reader-wordmark">maktaba</a>
      <nav class="reader-nav" aria-label="Primary">
        <a href="/library" class="reader-nav-link">library</a>
        <span class="reader-nav-link active">reading</span>
      </nav>
    </div>

    <div class="reader-topbar-center">
      <span class="tb-label">{readingProgressLabel}</span>
      <div class="tb-progress-track"><div class="tb-progress-fill" style={`width:${readingProgressPercent}%`}></div></div>
      <span class="tb-label">{readingProgressPercent}%</span>
      {#if jobStatus !== 'ready'}
        <span class="tb-status tb-status--{jobStatus}">{jobStatusLabel}</span>
      {/if}
    </div>

    <div class="reader-topbar-right">
      <!-- sr-only for tests -->
      <span class="sr-only">
        {#if highlightMode === 'text'}Select text directly in the PDF to save a highlight.{:else}Click and drag over the PDF to draw a highlight box.{/if}
      </span>

      <!-- Highlight mode dropdown -->
      <details class="tb-menu">
        <summary class="tb-summary">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"/></svg>
          {highlightMode === 'text' ? 'Select text' : 'Draw box'}
        </summary>
        <div class="tb-dropdown">
          <button class="tb-dropdown-item" class:tb-active={highlightMode === 'text'} on:click={() => setHighlightMode('text')}>Select text</button>
          <button class="tb-dropdown-item" class:tb-active={highlightMode === 'draw'} on:click={() => setHighlightMode('draw')}>Draw box</button>
        </div>
      </details>

      <!-- Page navigation -->
      <div class="tb-nav">
        <button class="tb-nav-btn" type="button" disabled={currentPage <= 1} on:click={goToPreviousPage} aria-label="Previous page">‹</button>
        <span class="tb-label tb-nav-page">{pageDisplay}</span>
        <button class="tb-nav-btn" type="button" disabled={currentPage >= totalPages} on:click={goToNextPage} aria-label="Next page">›</button>
      </div>

      <!-- Zoom dropdown -->
      <details class="tb-menu">
        <summary class="tb-summary">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>
          {zoomDisplay}
        </summary>
        <div class="tb-dropdown tb-dropdown--right">
          <button class="tb-dropdown-item" class:tb-active={zoomMode === 'fit-width'} on:click={setFitWidth}>Fit width</button>
          <button class="tb-dropdown-item" class:tb-active={zoomMode === 'fit-page'} on:click={setFitPage}>Fit page</button>
          <div class="tb-dropdown-divider"></div>
          <div class="tb-slider-row">
            <button class="tb-slider-btn" type="button" aria-label="Zoom out" on:click={zoomOut}>−</button>
            <input class="tb-slider" type="range" min={MIN_ZOOM * 100} max={MAX_ZOOM * 100} step="5"
              value={Math.round((zoomMode === 'custom' ? customZoom : currentScale) * 100)}
              on:input={handleZoomInput} aria-label="Zoom level"
            />
            <button class="tb-slider-btn" type="button" aria-label="Zoom in" on:click={zoomIn}>+</button>
          </div>
        </div>
      </details>

      <a class="tb-link" href={data.fileUrl} target="_blank" rel="noreferrer">↗ pdf</a>
    </div>
  </header>

  <div class="reader-workspace">
    <aside class="reader-sidebar paper-sidebar">
      <div class="paper-sidebar-tabs reader-sidebar-tabs">
        <span class="paper-tab active">notes</span>
        <span class="paper-tab">highlights</span>
        <span class="paper-tab">reader</span>
      </div>
      <div class="paper-search reader-sidebar-search">
        <input type="search" placeholder="search notes…" aria-label="Search notes" />
      </div>

      <section class="reader-highlights-panel">
        <p class="paper-sidebar-section-label">Highlights</p>

        {#if currentPageHighlights.length === 0}
          <p class="paper-sidebar-empty">No highlights on this page.</p>
        {:else}
          <ul class="paper-highlight-list">
            {#each currentPageHighlights as h, i (h.id ?? i)}
              <li class="paper-highlight-item">
                <span class="min-w-0 flex-1 truncate">{h.extracted_text || '(no text extracted)'}</span>
                <button
                  type="button"
                  class="paper-hl-note-btn"
                  aria-label={getPrimaryNoteForHighlight(h.id) ? 'Edit highlight note' : 'Add highlight note'}
                  on:click={() => void openHighlightNoteEditor(h.id, undefined, 'sidebar')}
                >
                  note
                </button>
                <button
                  type="button"
                  class="paper-hl-del-btn"
                  aria-label="Delete highlight"
                  on:click={() => promptDeleteHighlight(h)}
                >✕</button>
              </li>
            {/each}
          </ul>
        {/if}
      </section>

      <section data-testid="notes-sidebar" class="reader-notes-panel">
        <div class="paper-notes-header">
          <p class="paper-sidebar-section-label">Notes</p>
          <button
            type="button"
            class="paper-btn-accent paper-add-note-btn"
            on:click={() => void openDocumentNoteEditor()}
          >
            Add note
        </button>
      </div>

        {#if activeNoteTarget?.kind === 'document'}
          <NoteEditor
            placement="sidebar"
            initialContent={activeNoteRecord?.content ?? ''}
            highlight={null}
            onChange={(value) => {
              noteDraft = value;
            }}
            onSave={saveFromEditor}
            onClose={() => closeNoteEditor()}
            bind:this={noteEditorRef}
          />
        {:else if activeNoteTarget?.kind === 'highlight' && noteEditorPlacement === 'sidebar'}
          <NoteEditor
            placement="sidebar"
            initialContent={activeNoteRecord?.content ?? ''}
            highlight={activeNoteTarget.highlight}
            onChange={(value) => {
              noteDraft = value;
            }}
            onSave={saveFromEditor}
            onClose={() => closeNoteEditor()}
            bind:this={noteEditorRef}
          />
        {/if}

        {#if notesLoading}
          <p class="text-xs text-slate-500">Loading notes…</p>
        {:else if notesError}
          <p class="text-xs text-rose-300">{notesError}</p>
        {:else if noteSidebarGroups.documentNotes.length === 0 && noteSidebarGroups.pageGroups.length === 0}
          <p class="paper-sidebar-empty">No notes yet.</p>
        {:else}
          {#if noteSidebarGroups.documentNotes.length > 0}
            <p class="paper-note-group-label">Document notes</p>
            {#each noteSidebarGroups.documentNotes as note (note.id)}
              <div class="paper-note-item">
                <div class="paper-note-loc"><span class="paper-note-label">standalone</span></div>
                <div class="paper-note-body-row">
                  <button type="button" class="paper-note-body-btn" on:click={() => handleSidebarNoteClick(note)}>
                    <div class="paper-note-body">{note.content || '(empty note)'}</div>
                  </button>
                  <button type="button" class="paper-note-del" aria-label="Delete note" on:click={() => handleNoteDelete(note)}>✕</button>
                </div>
              </div>
            {/each}
          {/if}

          {#each noteSidebarGroups.pageGroups as group (group.pageNumber)}
            <p class="paper-note-group-label">Page {group.pageNumber}</p>
            {#each group.notes as note (note.id)}
              <div class="paper-note-item">
                {#if note.highlight?.extracted_text}
                  <div class="paper-note-quote">&ldquo;{note.highlight.extracted_text}&rdquo;</div>
                {/if}
                <div class="paper-note-body-row">
                  <button type="button" class="paper-note-body-btn" on:click={() => handleSidebarNoteClick(note)}>
                    <div class="paper-note-body">{note.content || '(empty note)'}</div>
                  </button>
                  <button type="button" class="paper-note-del" aria-label="Delete note" on:click={() => handleNoteDelete(note)}>✕</button>
                </div>
              </div>
            {/each}
          {/each}
        {/if}
      </section>

    </aside>

    <section class="reader-stage">
      <div class="reader-meta">
        <p class="reader-kicker">PDF reader</p>
        <h1 class="reader-title">{documentTitle}</h1>
        <p class="reader-authors">{authorsLabel}</p>
      </div>

      <div class="reader-stage-card rounded-3xl border border-slate-700/80 bg-slate-950/70 shadow-2xl shadow-cyan-950/10">
        <div class="reader-stage-header flex items-center justify-between border-b border-slate-800 px-5 py-4 text-sm text-slate-400">
          <div>{documentTitle}</div>
          <div>{pageDisplay}</div>
        </div>
        <div class="reader-stage-body">
        <div bind:this={pdfViewerHostEl} class="reader-pdf-shell relative h-full overflow-hidden rounded-2xl bg-slate-900/60">
          {#if browser}
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
                    editHighlightPopup={editHighlightPopup as any}
                    onHighlightsRendered={handleHighlighterRendered}
                    scaleOnResize={true}
                    style="width: 100%; height: 100%; background: rgb(15 23 42);"
                  />
                {/snippet}
              </PdfLoader>
            {/if}
          {:else}
            <div class="flex h-full items-center justify-center p-6 text-sm text-slate-400">
              Loading reader…
            </div>
          {/if}
        </div>
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
