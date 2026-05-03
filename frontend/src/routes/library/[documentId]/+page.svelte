<script lang="ts">
  import { browser } from '$app/environment';
  import { beforeNavigate, goto, replaceState } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount, tick } from 'svelte';
  import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
  import {
    PdfLoader,
    PdfHighlighter,
    HighlightsModel,
    type PdfHighlighterUtils,
  } from 'svelte-pdf-highlighter';
  import { computeProgressPercent } from '../../../lib/progress';
  import {
    backendToLibraryHighlight,
    buildCreatePayload,
    createHighlightClient,
    createNoteClient,
    type BackendHighlight,
    type BackendHighlightColor,
    type BackendNote,
    type HighlightCreatePayload,
    type LibraryHighlight,
  } from './highlight-api';
  import NoteEditor from '../../../components/NoteEditor.svelte';
  import { popupViewportGuard } from '$lib/popup-viewport-guard';

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
  type HighlightMode = 'off' | 'text' | 'draw';
  type JobStatus = 'ready' | 'processing' | 'failed';
  type SidebarMode = 'annotations' | 'document-notes';

  type PopupHighlightLike = {
    id?: string;
    comment?: string | null;
    extracted_text?: string | null;
    color?: BackendHighlightColor | null;
    content?: { text?: string };
  };

  type NoteEditorTarget =
    | { kind: 'highlight'; highlight: BackendHighlight }
    | { kind: 'document' };

  type NoteGroup = {
    pageNumber: number;
    notes: BackendNote[];
  };

  type HighlightGroup = {
    pageNumber: number;
    highlights: BackendHighlight[];
  };

  type QueryJumpTarget = {
    highlightId: string | null;
    pageNumber: number | null;
  };

  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 3;
  const ZOOM_STEP = 0.1;
  const PDF_WORKER_SRC = pdfWorkerSrc;
  const HIGHLIGHT_COLOR_OPTIONS: Array<{
    name: BackendHighlightColor;
    label: string;
    hex: string;
  }> = [
    { name: 'yellow', label: 'Yellow', hex: '#fde047' },
    { name: 'green', label: 'Green', hex: '#bbf7d0' },
    { name: 'blue', label: 'Blue', hex: '#bfdbfe' },
    { name: 'red', label: 'Red', hex: '#fecaca' },
  ];
  const DEFAULT_HIGHLIGHT_COLOR_INDEX = 0;
  const BLOCKING_JOB_TYPES = new Set(['extract_text', 'ocr']);

  let loading = true;
  let error: string | null = null;
  let statusMessage = 'Loading PDF…';
  let currentPage = 1;
  let totalPages = data.document.page_count ?? 0;
  let maxPageReached = 1;
  let pageJumpDraft = '1';
  let pageJumpFocused = false;

  function loadProgress() {
    try {
      const raw = localStorage.getItem(`maktaba:progress:${data.document.id}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        maxPageReached = Math.max(1, Math.min(totalPages || Infinity, Number(parsed.maxPage) || Number(parsed.page) || 1));
        const savedPage = Number(parsed.lastPage) || Number(parsed.page) || 1;
        currentPage = Math.max(1, Math.min(totalPages || Infinity, savedPage));
      }
    } catch {
      maxPageReached = 1;
    }
  }

  function saveProgress() {
    try {
      localStorage.setItem(
        `maktaba:progress:${data.document.id}`,
        JSON.stringify({ lastPage: currentPage, maxPage: maxPageReached, total: totalPages }),
      );
    } catch {}
  }

  const highlightLocatorCacheKey = `maktaba:highlight-locators:${data.document.id}`;

  type CachedHighlightLocator = Pick<
    HighlightCreatePayload,
    'page_number' | 'x' | 'y' | 'width' | 'height' | 'extracted_text' | 'highlight_type' | 'rects'
  >;

  function readHighlightLocatorCache(): Record<string, CachedHighlightLocator> {
    if (!browser) return {};
    try {
      return JSON.parse(localStorage.getItem(highlightLocatorCacheKey) || '{}');
    } catch {
      return {};
    }
  }

  function cacheHighlightLocator(highlightId: string, payload: HighlightCreatePayload) {
    if (!browser || !highlightId) return;
    try {
      const cache = readHighlightLocatorCache();
      cache[highlightId] = {
        page_number: payload.page_number,
        x: payload.x,
        y: payload.y,
        width: payload.width,
        height: payload.height,
        extracted_text: payload.extracted_text,
        highlight_type: payload.highlight_type,
        rects: payload.rects,
      };
      localStorage.setItem(highlightLocatorCacheKey, JSON.stringify(cache));
    } catch {}
  }

  function mergeCachedHighlightLocator(highlight: BackendHighlight): BackendHighlight {
    const cached = readHighlightLocatorCache()[highlight.id];
    if (!cached) return highlight;
    const shouldUseCachedTextLocator = cached.highlight_type === 'text' && (cached.rects?.length ?? 0) > 0;
    if (!shouldUseCachedTextLocator) return highlight;

    return {
      ...highlight,
      page_number: cached.page_number,
      x: cached.x,
      y: cached.y,
      width: cached.width,
      height: cached.height,
      extracted_text: cached.extracted_text || highlight.extracted_text,
      highlight_type: 'text',
      rects: cached.rects,
    };
  }

  $: if (totalPages > 0 && maxPageReached === 1) loadProgress();
  $: if (currentPage > maxPageReached) {
    maxPageReached = currentPage;
    saveProgress();
  }
  beforeNavigate(() => {
    saveProgress();
  });
  let zoomMode: ZoomMode = 'fit-width';
  let highlightMode: HighlightMode = 'off';
  let lastHighlightMode: Exclude<HighlightMode, 'off'> = 'text';
  let customZoom = 1;
  let currentScale = 1;
  let pdfViewerHostEl: HTMLDivElement | null = null;
  let pdfScrollerEl: HTMLElement | null = null;
  let scrollFrame: number | null = null;
  let highlightsRefreshFrame: number | null = null;
  let queryJumpFrame: number | null = null;
  let initialZoomApplied = false;
  let initialPageRestored = false;
  let pendingQueryJumpTarget: QueryJumpTarget | null = null;
  let queryJumpDataLoaded = false;
  let queryJumpApplied = false;

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
  let highlightSidebarGroups: HighlightGroup[] = [];
  let filteredHighlightSidebarGroups: HighlightGroup[] = [];
  let filteredDocumentNotes: BackendNote[] = [];
  let sidebarMode: SidebarMode = 'annotations';
  let sidebarSearchQuery = '';
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
  let noteEditorRef: any = null;
  let popupNoteStatus: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
  const popupPinnedSetterByHighlightId = new Map<string, (flag: boolean) => void>();
  const backendHighlightIdByStoreId = new Map<string, string>();

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

  let selectedHighlightColorIndex = DEFAULT_HIGHLIGHT_COLOR_INDEX;
  let pdfHighlighterUtils: Partial<PdfHighlighterUtils> = {
    selectedTool: 'text_selection',
    selectedColorIndex: selectedHighlightColorIndex,
    colors: HIGHLIGHT_COLOR_OPTIONS.map((option) => option.hex),
    highlightMixBlendMode: 'multiply',
    textSelectionDelay: -1,
  };

  $: documentTitle = data.document.title ?? 'Untitled';
  $: authorsLabel = data.document.authors && data.document.authors.length > 0
    ? data.document.authors.join(', ')
    : 'Unknown author';
  $: readingProgressPercent = computeProgressPercent(currentPage, totalPages);
  $: if (!pageJumpFocused) pageJumpDraft = String(currentPage);
  $: readingProgressComplete = readingProgressPercent >= 100;
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
  $: noteSidebarGroups = groupNotesForSidebar(notes);
  // Include notes in dependencies so highlight cards re-render when attached notes change
  $: highlightSidebarGroups = (notes.length, groupHighlightsForSidebar(highlights));
  $: filteredHighlightSidebarGroups = filterHighlightGroups(highlightSidebarGroups, sidebarSearchQuery);
  $: filteredDocumentNotes = filterDocumentNotesForSidebar(noteSidebarGroups.documentNotes, sidebarSearchQuery);

  function clampZoom(value: number) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  }

  function clampColorIndex(value: number) {
    return Math.min(HIGHLIGHT_COLOR_OPTIONS.length - 1, Math.max(0, value));
  }

  function colorIndexFromName(color: string | null | undefined): number {
    const normalized = (color || '').toLowerCase();
    const found = HIGHLIGHT_COLOR_OPTIONS.findIndex((option) => option.name === normalized);
    return found >= 0 ? found : DEFAULT_HIGHLIGHT_COLOR_INDEX;
  }

  function colorNameFromIndex(index: number): BackendHighlightColor {
    return HIGHLIGHT_COLOR_OPTIONS[clampColorIndex(index)]?.name ?? HIGHLIGHT_COLOR_OPTIONS[DEFAULT_HIGHLIGHT_COLOR_INDEX].name;
  }

  function getCurrentColorIndex(): number {
    const raw = (pdfHighlighterUtils as any)?.selectedColorIndex;
    const fallback = typeof selectedHighlightColorIndex === 'number' ? selectedHighlightColorIndex : DEFAULT_HIGHLIGHT_COLOR_INDEX;
    return clampColorIndex(typeof raw === 'number' ? raw : fallback);
  }

  function setSelectedHighlightColor(index: number) {
    const clamped = clampColorIndex(index);
    selectedHighlightColorIndex = clamped;
    pdfHighlighterUtils = {
      ...pdfHighlighterUtils,
      selectedColorIndex: clamped,
      colors: HIGHLIGHT_COLOR_OPTIONS.map((option) => option.hex),
      highlightMixBlendMode: 'multiply',
      textSelectionDelay: -1,
    };
  }

  function getHighlightColorName(highlight: BackendHighlight | null | undefined): BackendHighlightColor {
    if (highlight?.color) {
      return colorNameFromIndex(colorIndexFromName(highlight.color));
    }
    return colorNameFromIndex(getCurrentColorIndex());
  }

  function getHighlightColorHex(highlight: BackendHighlight | null | undefined): string {
    const colorName = getHighlightColorName(highlight);
    return HIGHLIGHT_COLOR_OPTIONS.find((option) => option.name === colorName)?.hex ?? HIGHLIGHT_COLOR_OPTIONS[DEFAULT_HIGHLIGHT_COLOR_INDEX].hex;
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

  function getNoteSortPage(note: BackendNote): number {
    return getNotePageNumber(note) ?? Number.POSITIVE_INFINITY;
  }

  function getNoteSortTimestamp(note: BackendNote): number {
    return Date.parse(note.updated_at || note.created_at || '') || 0;
  }

  function compareNotes(a: BackendNote, b: BackendNote): number {
    return (
      getNoteSortPage(a) - getNoteSortPage(b) ||
      getNoteSortTimestamp(b) - getNoteSortTimestamp(a) ||
      a.id.localeCompare(b.id)
    );
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

  function groupHighlightsForSidebar(records: BackendHighlight[] = []): HighlightGroup[] {
    const pageBuckets = new Map<number, BackendHighlight[]>();

    for (const highlight of records) {
      const pageNumber = highlight.page_number;
      const bucket = pageBuckets.get(pageNumber) ?? [];
      bucket.push(highlight);
      pageBuckets.set(pageNumber, bucket);
    }

    return [...pageBuckets.entries()]
      .sort(([pageA], [pageB]) => pageA - pageB)
      .map(([pageNumber, pageHighlights]) => ({
        pageNumber,
        highlights: [...pageHighlights].sort((a, b) => a.id.localeCompare(b.id)),
      }));
  }

  function getPrimaryNoteForHighlight(highlightId: string | undefined | null) {
    return getNotesForHighlight(highlightId)[0] ?? null;
  }

  function normalizeSidebarSearch(value: string | null | undefined) {
    return (value ?? '').trim().toLowerCase();
  }

  function matchesSidebarSearch(query: string, ...parts: Array<string | null | undefined>) {
    if (!query) return true;
    return parts.some((part) => (part ?? '').toLowerCase().includes(query));
  }

  function filterHighlightGroups(groups: HighlightGroup[] = [], rawQuery = ''): HighlightGroup[] {
    const query = normalizeSidebarSearch(rawQuery);
    if (!query) return groups;

    return groups
      .map((group) => ({
        ...group,
        highlights: group.highlights.filter((highlight) => {
          const note = getPrimaryNoteForHighlight(highlight.id);
          return matchesSidebarSearch(query, highlight.extracted_text, note?.content);
        }),
      }))
      .filter((group) => group.highlights.length > 0);
  }

  function filterDocumentNotesForSidebar(records: BackendNote[] = [], rawQuery = ''): BackendNote[] {
    const query = normalizeSidebarSearch(rawQuery);
    if (!query) return records;
    return records.filter((note) => matchesSidebarSearch(query, note.content));
  }

  function resolveBackendHighlightId(highlightId: string | undefined | null) {
    if (!highlightId) return '';
    if (highlights.some((highlight) => highlight.id === highlightId)) return highlightId;
    return backendHighlightIdByStoreId.get(highlightId) ?? highlightId;
  }

  function getHighlightById(highlightId: string | undefined | null) {
    const resolvedHighlightId = resolveBackendHighlightId(highlightId);
    if (!resolvedHighlightId) return null;
    return highlights.find((highlight) => highlight.id === resolvedHighlightId) ?? null;
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

  function shouldSkipBlankNewNote(note: BackendNote | null, draft: string): boolean {
    return note === null && draft.trim().length === 0;
  }

  async function saveNoteDraft(target: NoteEditorTarget, note: BackendNote | null, draft: string) {
    if (note) {
      return await noteClient.updateNote(note.id, { content: draft });
    }

    return await noteClient.createNote({
      content: draft,
      highlight_id: target.kind === 'highlight' ? target.highlight.id : null,
    });
  }

  function syncSavedNoteToActiveEditor(savedNote: BackendNote, target: NoteEditorTarget, revision: number) {
    if (revision !== noteEditorRevision) return;
    activeNoteRecord = savedNote;
    noteDraft = savedNote.content;
    noteSavedDraft = savedNote.content;
    setNoteStatus('saved', 'Saved');
    scheduleSavedNoteFade(revision, target);
  }

  function handleNoteSaveFailure(error: unknown, revision: number) {
    console.error('[note] Failed to save note', error);
    if (revision === noteEditorRevision) {
      setNoteStatus('error', 'Unable to save note');
    }
  }

  async function persistNoteDraft(
    target: NoteEditorTarget,
    note: BackendNote | null,
    draft: string,
    revision: number,
  ) {
    if (shouldSkipBlankNewNote(note, draft)) {
      if (revision === noteEditorRevision) resetNoteStatus(target);
      return null;
    }

    if (revision === noteEditorRevision) setNoteStatus('saving', 'Saving…');

    try {
      const savedNote = await saveNoteDraft(target, note, draft);
      upsertNote(savedNote);
      syncSavedNoteToActiveEditor(savedNote, target, revision);
      return savedNote;
    } catch (e) {
      handleNoteSaveFailure(e, revision);
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
    if (placement === 'sidebar') {
      sidebarMode = 'annotations';
    }
    if (placement === 'popup') {
      setPinned?.(true);
    }
    await openNoteEditor({ kind: 'highlight', highlight }, getPrimaryNoteForHighlight(highlight.id));
  }

  async function openDocumentNoteEditor(note: BackendNote | null = null) {
    sidebarMode = 'document-notes';
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

  function scrollHighlightIntoView(highlight: BackendHighlight) {
    currentPage = Math.min(Math.max(highlight.page_number, 1), totalPages || highlight.page_number);

    if (pdfHighlighterUtils.scrollToHighlight) {
      try {
        pdfHighlighterUtils.scrollToHighlight(backendToLibraryHighlight(highlight));
        window.setTimeout(updateCurrentPageFromScroll, 120);
        window.setTimeout(updateCurrentPageFromScroll, 520);
        if (totalPages > 0) {
          statusMessage = `Showing page ${currentPage} of ${totalPages}`;
        }
        return true;
      } catch (e) {
        console.warn('[highlight] pdfHighlighterUtils.scrollToHighlight failed', e);
      }
    }

    ensurePdfScroller();
    if (!pdfScrollerEl) return false;
    const pageEl = pdfScrollerEl.querySelector<HTMLElement>(`.page[data-page-number="${currentPage}"]`);
    if (!pageEl) return false;

    pageEl.scrollIntoView({ block: 'start', behavior: 'smooth' });
    window.setTimeout(updateCurrentPageFromScroll, 520);
    return true;
  }

  function findHighlightElement(highlightId: string): HTMLElement | null {
    return (
      (pdfViewerHostEl?.querySelector(`[data-testid="mock-highlight-${highlightId}"]`) as HTMLElement | null) ||
      (pdfViewerHostEl?.querySelector(`[data-highlight-id="${highlightId}"]`) as HTMLElement | null) ||
      (document.getElementById(String(highlightId)) as HTMLElement | null) ||
      findHighlightElementByIdAttribute(highlightId)
    );
  }

  function findHighlightElementByIdAttribute(highlightId: string): HTMLElement | null {
    try {
      const escaped = String(highlightId).replace(/"/g, '\\"');
      return pdfViewerHostEl?.querySelector(`[id="${escaped}"]`) as HTMLElement | null;
    } catch {
      return null;
    }
  }

  function scrollHighlightElementIntoView(el: HTMLElement, enabled: boolean) {
    if (!enabled) return;
    try {
      el.scrollIntoView?.({ block: 'center', behavior: 'smooth' } as any);
    } catch {}
  }

  function decorateFocusedHighlight(el: HTMLElement) {
    const previousOutline = el.style.outline;
    const previousOutlineOffset = el.style.outlineOffset;
    const previousTabIndex = el.getAttribute('tabindex');
    if (previousTabIndex === null) el.setAttribute('tabindex', '-1');

    try {
      el.focus?.({ preventScroll: true } as any);
    } catch {}

    el.style.outline = '2px solid rgb(34 211 238 / 0.9)';
    el.style.outlineOffset = '2px';
    window.setTimeout(() => restoreHighlightDecoration(el, previousOutline, previousOutlineOffset, previousTabIndex), 1200);
  }

  function restoreHighlightDecoration(
    el: HTMLElement,
    previousOutline: string,
    previousOutlineOffset: string,
    previousTabIndex: string | null,
  ) {
    el.style.outline = previousOutline;
    el.style.outlineOffset = previousOutlineOffset;
    if (previousTabIndex === null) el.removeAttribute('tabindex');
  }

  function activateHighlightElement(el: HTMLElement) {
    try {
      el.click?.();
    } catch {}
  }

  function rememberPopupPinnedSetter(highlightId: string, setPinned: (flag: boolean) => void) {
    if (highlightId) {
      popupPinnedSetterByHighlightId.set(highlightId, setPinned);
    }
    return true;
  }

  function getPopupPinnedSetter(highlightId: string) {
    return popupPinnedSetterByHighlightId.get(highlightId);
  }

  async function savePopupHighlightNote(highlightId: string, draft: string) {
    const backendHighlightId = resolveBackendHighlightId(highlightId);
    const highlight = getHighlightById(backendHighlightId);
    if (!highlight) return null;
    const note = getPrimaryNoteForHighlight(backendHighlightId);
    if (shouldSkipBlankNewNote(note, draft)) return draft;

    try {
      const savedNote = await saveNoteDraft({ kind: 'highlight', highlight }, note, draft);
      upsertNote(savedNote);
      return savedNote;
    } catch (error) {
      console.error('[note] Failed to save popup note', error);
      return null;
    }
  }

  function openHighlightPopupAfterFocus(highlightId: string, enabled: boolean | undefined) {
    if (!enabled) return;
    setTimeout(() => {
      getPopupPinnedSetter(highlightId)?.(true);
      window.setTimeout(() => {
        const textarea = document.querySelector<HTMLTextAreaElement>('.hl_tip_container textarea');
        textarea?.focus({ preventScroll: true });
      }, 30);
    }, 0);
  }

  async function focusHighlightById(highlightId: string, options: { openPopup?: boolean; scrollIntoView?: boolean } = {}) {
    await tick();
    const el = findHighlightElement(highlightId);
    if (!el) return false;

    scrollHighlightElementIntoView(el, options.scrollIntoView !== false);
    decorateFocusedHighlight(el);
    activateHighlightElement(el);
    openHighlightPopupAfterFocus(highlightId, options.openPopup);
    return true;
  }

  async function handleSidebarHighlightClick(highlight: BackendHighlight) {
    const didScroll = scrollHighlightIntoView(highlight);
    if (!didScroll) {
      scrollToPage(highlight.page_number);
    }
    statusMessage = `Jumped to page ${highlight.page_number}`;
    window.setTimeout(() => {
      void focusHighlightById(highlight.id, { scrollIntoView: false });
    }, 180);
  }

  async function handleSidebarNoteClick(note: BackendNote) {
    const pageNumber = getNotePageNumber(note);
    if (pageNumber === null) {
      void openDocumentNoteEditor(note);
      return;
    }

    const noteHighlight = note.highlight_id ? getHighlightById(note.highlight_id) ?? note.highlight : null;
    if (noteHighlight) {
      const didScroll = scrollHighlightIntoView(noteHighlight);
      if (!didScroll) {
        scrollToPage(pageNumber);
      }
    } else {
      scrollToPage(pageNumber);
    }
    statusMessage = `Jumped to page ${pageNumber}`;

    if (note.highlight_id) {
      window.setTimeout(() => {
        void focusHighlightById(note.highlight_id as string, { openPopup: true, scrollIntoView: false });
      }, 180);
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

  function persistPendingStoreHighlights(storeHighlights: LibraryHighlight[]) {
    for (const highlight of storeHighlights) {
      if (highlight.serverPersisted) continue;
      const highlightId = highlight.id ?? '';
      if (!highlightId || pendingHighlightIds.has(highlightId)) continue;
      void persistLibraryHighlight(highlight);
    }
  }

  function getHighlightStoreIds(storeHighlights: LibraryHighlight[]) {
    return new Set(
      storeHighlights
        .map((highlight) => highlight.id)
        .filter((highlightId): highlightId is string => typeof highlightId === 'string' && highlightId.length > 0),
    );
  }

  function deleteMissingPersistedHighlights(storeIds: Set<string>) {
    for (const persistedHighlight of highlights) {
      if (storeIds.has(persistedHighlight.id) || pendingDeleteIds.has(persistedHighlight.id)) continue;
      void deleteHighlightById(persistedHighlight.id, { suppressAlert: true });
    }
  }

  function handleHighlightsStoreUpdate(storeHighlights: LibraryHighlight[]) {
    if (rebuildingHighlightsStore) return;
    persistPendingStoreHighlights(storeHighlights);
    deleteMissingPersistedHighlights(getHighlightStoreIds(storeHighlights));
  }

  function subscribeToHighlightsStore() {
    unsubscribeHighlightsStore?.();
    unsubscribeHighlightsStore = highlightsStore.subscribe(handleHighlightsStoreUpdate);
  }

  async function loadHighlights() {
    try {
      highlights = (await highlightClient.fetchHighlights()).map(mergeCachedHighlightLocator);
      syncHighlightsStore();
    } catch (e) {
      console.error('[highlight] Failed to load highlights', e);
    }
  }

  function readQueryJumpTarget(): QueryJumpTarget | null {
    if (!browser) return null;
    const params = new URLSearchParams(window.location.search);
    const highlightId = params.get('highlight');
    const pageParam = params.get('page');
    const pageNumber = pageParam ? Number(pageParam) : null;
    const validPageNumber = pageNumber && !Number.isNaN(pageNumber) && pageNumber > 0 ? pageNumber : null;
    if (!highlightId && !validPageNumber) return null;
    return { highlightId, pageNumber: validPageNumber };
  }

  function clearQueryJumpParams() {
    if (!browser) return;
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('highlight');
      url.searchParams.delete('page');
      replaceState(url.pathname + url.search + url.hash, $page.state);
    } catch {}
  }

  async function applyQueryJumpTarget(target: QueryJumpTarget) {
    await tick();
    ensurePdfScroller();
    if (!pdfScrollerEl) return false;

    if (target.highlightId) {
      const highlight = getHighlightById(target.highlightId);
      if (!highlight) return false;
      const didScroll = scrollHighlightIntoView(highlight) || scrollToPage(highlight.page_number);
      if (!didScroll) return false;
      window.setTimeout(() => {
        void focusHighlightById(target.highlightId as string, { openPopup: true, scrollIntoView: false });
      }, 280);
      return true;
    }

    if (target.pageNumber) {
      return scrollToPage(target.pageNumber);
    }

    return false;
  }

  function scheduleQueryJump() {
    if (!browser || !pendingQueryJumpTarget || !queryJumpDataLoaded || queryJumpApplied || queryJumpFrame !== null) return;
    ensurePdfScroller();
    if (!pdfScrollerEl) return;

    queryJumpFrame = window.requestAnimationFrame(() => {
      queryJumpFrame = window.requestAnimationFrame(() => {
        queryJumpFrame = null;
        const target = pendingQueryJumpTarget;
        if (!target || queryJumpApplied) return;
        void applyQueryJumpTarget(target).then((didJump) => {
          if (!didJump) return;
          queryJumpApplied = true;
          pendingQueryJumpTarget = null;
          clearQueryJumpParams();
        });
      });
    });
  }

  async function persistLibraryHighlight(highlight: LibraryHighlight) {
    const highlightId = highlight.id ?? '';
    const payload = buildCreatePayload(highlight);

    if (!payload) {
      highlightsStore.deleteHighlight(highlight);
      return;
    }

    const colorIndexFromHighlight = typeof (highlight as any).color_index === 'number'
      ? clampColorIndex((highlight as any).color_index)
      : getCurrentColorIndex();
    payload.color = colorNameFromIndex(colorIndexFromHighlight);

    pendingHighlightIds.add(highlightId);
    statusMessage = `Saving highlight on page ${payload.page_number}…`;

    try {
      const createdHighlight = await highlightClient.createHighlight(payload);
      cacheHighlightLocator(createdHighlight.id, payload);
      const mergedCreatedHighlight = mergeCachedHighlightLocator(createdHighlight);
      highlights = [...highlights, mergedCreatedHighlight];
      if (highlightId) {
        backendHighlightIdByStoreId.set(highlightId, createdHighlight.id);
        highlightsStore.editHighlight(highlightId, {
          id: createdHighlight.id,
          color_index: colorIndexFromName(createdHighlight.color),
          serverPersisted: true,
        } as Partial<LibraryHighlight>);
      }
      currentPage = mergedCreatedHighlight.page_number;
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

  async function updateHighlightColor(highlightId: string, color: BackendHighlightColor, setPinned?: (flag: boolean) => void) {
    const backendHighlightId = resolveBackendHighlightId(highlightId);
    const colorIndex = colorIndexFromName(color);
    setSelectedHighlightColor(colorIndex);

    try {
      const updatedHighlight = mergeCachedHighlightLocator(await highlightClient.updateHighlight(backendHighlightId, { color }));
      highlights = highlights.map((highlight) =>
        highlight.id === backendHighlightId ? updatedHighlight : highlight,
      );
      highlightsStore.editHighlight(highlightId, {
        color_index: colorIndexFromName(updatedHighlight.color),
      } as Partial<LibraryHighlight>);
      statusMessage = 'Highlight color updated';
    } catch (e) {
      console.error('[highlight] update color error', e);
      alert('Unable to update highlight color');
      statusMessage = 'Unable to update highlight color';
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

  function getViewerPages(): HTMLElement[] {
    return pdfScrollerEl ? Array.from(pdfScrollerEl.querySelectorAll<HTMLElement>('.page[data-page-number]')) : [];
  }

  function getScrollAnchor(containerRect: DOMRect) {
    return containerRect.top + Math.min(140, Math.max(72, containerRect.height * 0.22));
  }

  function getPageNumberFromElement(page: HTMLElement): number | null {
    const pageNumber = Number(page.dataset.pageNumber || '0');
    return pageNumber > 0 ? pageNumber : null;
  }

  function getPageVisibleArea(rect: DOMRect, containerRect: DOMRect) {
    const visibleTop = Math.max(rect.top, containerRect.top);
    const visibleBottom = Math.min(rect.bottom, containerRect.bottom);
    return Math.max(0, visibleBottom - visibleTop);
  }

  function chooseScrolledPage(pages: HTMLElement[], containerRect: DOMRect, fallbackPage: number) {
    const anchor = getScrollAnchor(containerRect);
    let bestPage = fallbackPage;
    let bestVisibleArea = -1;
    let bestScore = Number.POSITIVE_INFINITY;

    for (const page of pages) {
      const pageNumber = getPageNumberFromElement(page);
      if (!pageNumber) continue;

      const rect = page.getBoundingClientRect();
      if (rect.top <= anchor && rect.bottom >= anchor) return pageNumber;

      const visibleArea = getPageVisibleArea(rect, containerRect);
      const score = Math.abs(rect.top - anchor);
      if (visibleArea > bestVisibleArea || (visibleArea === bestVisibleArea && score < bestScore)) {
        bestVisibleArea = visibleArea;
        bestScore = score;
        bestPage = pageNumber;
      }
    }

    return bestPage;
  }

  function setCurrentPageFromScroll(nextPage: number) {
    if (nextPage !== currentPage) currentPage = nextPage;
    if (totalPages > 0) {
      statusMessage = `Showing page ${currentPage} of ${totalPages}`;
    }
  }

  function updateCurrentPageFromScroll() {
    if (!pdfScrollerEl) return;
    const pages = getViewerPages();
    if (pages.length === 0) return;
    const nextPage = chooseScrolledPage(pages, pdfScrollerEl.getBoundingClientRect(), currentPage);
    setCurrentPageFromScroll(nextPage);
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
      scheduleQueryJump();
      // Restore scroll to the last viewed page only once after initial PDF layout settles.
      // Re-running this on later highlight/text-layer renders can yank the reader while scrolling
      // past image-heavy pages, freshly rendered highlight layers, or explicit search-result jumps.
      if (!initialPageRestored && !pendingQueryJumpTarget) {
        initialPageRestored = true;
        const savedPage = currentPage;
        if (savedPage > 1 && pdfScrollerEl) {
          window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
              const pageEl = pdfScrollerEl?.querySelector<HTMLElement>(`.page[data-page-number="${savedPage}"]`);
              if (pageEl) {
                pageEl.scrollIntoView({ block: 'start', behavior: 'auto' });
                currentPage = savedPage;
                if (totalPages > 0) {
                  statusMessage = `Showing page ${currentPage} of ${totalPages}`;
                }
              }
            });
          });
        }
      }
    });
  }

  function handlePdfLoadError(loadError: Error) {
    error = loadError.message;
    loading = false;
    statusMessage = 'Unable to open the PDF';
  }

  function setHighlightMode(mode: HighlightMode) {
    highlightMode = mode;
    if (mode !== 'off') lastHighlightMode = mode;
    pdfHighlighterUtils = {
      ...pdfHighlighterUtils,
      selectedTool: mode === 'text' ? 'highlight_pen' : mode === 'draw' ? 'area_selection' : 'text_selection',
      selectedColorIndex: getCurrentColorIndex(),
      colors: HIGHLIGHT_COLOR_OPTIONS.map((option) => option.hex),
      highlightMixBlendMode: 'multiply',
      textSelectionDelay: mode === 'off' ? 1500 : -1,
    };
    statusMessage = mode === 'text'
      ? 'Select text directly in the PDF to save a highlight.'
      : mode === 'draw'
        ? 'Click and drag over the PDF to draw a highlight box.'
        : 'Highlighting is off.';
  }

  function toggleHighlightTools() {
    setHighlightMode(highlightMode === 'off' ? lastHighlightMode : 'off');
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
    if (!pdfScrollerEl) return false;
    const clampedPage = Math.min(Math.max(pageNumber, 1), totalPages || pageNumber);
    const pageEl = pdfScrollerEl.querySelector<HTMLElement>(`.page[data-page-number="${clampedPage}"]`);
    if (!pageEl) return false;
    currentPage = clampedPage;
    pageEl.scrollIntoView({ block: 'start', behavior: 'smooth' });
    if (totalPages > 0) {
      statusMessage = `Showing page ${currentPage} of ${totalPages}`;
    }
    return true;
  }

  function goToPreviousPage() {
    if (currentPage <= 1) return;
    scrollToPage(currentPage - 1);
  }

  function goToNextPage() {
    if (currentPage >= totalPages) return;
    scrollToPage(currentPage + 1);
  }

  function resetPageJumpDraft() {
    pageJumpDraft = String(currentPage);
  }

  function commitPageJump() {
    const requestedPage = Number.parseInt(pageJumpDraft, 10);
    if (!Number.isFinite(requestedPage)) {
      resetPageJumpDraft();
      return;
    }
    scrollToPage(Math.min(Math.max(requestedPage, 1), totalPages || requestedPage));
  }

  function handlePageJumpKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault();
      commitPageJump();
      (event.currentTarget as HTMLInputElement).blur();
    } else if (event.key === 'Escape') {
      resetPageJumpDraft();
      (event.currentTarget as HTMLInputElement).blur();
    }
  }

  function handleReadingProgressClick(event: MouseEvent) {
    if (!totalPages) return;
    const track = event.currentTarget as HTMLButtonElement;
    const rect = track.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    scrollToPage(Math.min(totalPages, Math.max(1, Math.floor(ratio * totalPages) + 1)));
  }

  onMount(() => {
    if (typeof window !== 'undefined') {
      window.scrollTo(0, 0);
      history.scrollRestoration = 'manual';
      pendingQueryJumpTarget = readQueryJumpTarget();
      if (pendingQueryJumpTarget) {
        initialPageRestored = true;
      }
      try {
        localStorage.setItem('maktaba:lastDocumentId', data.document.id);
      } catch {}
    }
    subscribeToHighlightsStore();
    syncHighlightsStore();
    void loadHighlights().then(() => {
      void loadNotes().then(() => {
        queryJumpDataLoaded = true;
        scheduleQueryJump();
      });
    });
    setHighlightMode('off');

    const handleBeforeUnload = () => saveProgress();
    const progressSaveInterval = window.setInterval(saveProgress, 5000);
    window.addEventListener('beforeunload', handleBeforeUnload);

    function handleDocumentClick(event: MouseEvent) {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const openMenus = document.querySelectorAll<HTMLDetailsElement>('details.tb-menu[open]');
      for (const menu of openMenus) {
        if (!menu.contains(target)) {
          menu.open = false;
        }
      }
    }
    document.addEventListener('click', handleDocumentClick, true);

    return () => {
      unsubscribeHighlightsStore?.();
      disconnectPdfScroller();
      clearNoteTimers();
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.clearInterval(progressSaveInterval);
      document.removeEventListener('click', handleDocumentClick, true);
      if (typeof window !== 'undefined') {
        if (scrollFrame !== null) {
          window.cancelAnimationFrame(scrollFrame);
        }
        if (highlightsRefreshFrame !== null) {
          window.cancelAnimationFrame(highlightsRefreshFrame);
        }
        if (queryJumpFrame !== null) {
          window.cancelAnimationFrame(queryJumpFrame);
        }
      }
    };
  });
</script>



{#snippet inlineHighlightPopup(highlight: PopupHighlightLike, setPinned: ((flag: boolean) => void) | undefined, autoFocus = false)}
  {@const storeHighlightId = highlight.id ?? ''}
  {@const highlightId = resolveBackendHighlightId(storeHighlightId)}
  {@const _remembered = setPinned ? rememberPopupPinnedSetter(highlightId, setPinned) : true}
  {@const backendHighlight = getHighlightById(highlightId)}
  <div class="Highlight__popup hp-popup" use:popupViewportGuard>
    <div class="hp-section hp-section--actions">
      <div class="hp-row">
        <span class="hp-label-group">
          <span class="hp-label">note</span>
          {#if popupNoteStatus === 'saving'}
            <span class="hp-save-dot hp-save-dot--saving" role="status" aria-label="Saving" title="Saving…"></span>
          {:else if popupNoteStatus === 'saved'}
            <span class="hp-save-dot hp-save-dot--saved" role="status" aria-label="Saved" title="Saved"></span>
          {:else if popupNoteStatus === 'error'}
            <span class="hp-save-dot hp-save-dot--error" role="status" aria-label="Error" title="Unable to save"></span>
          {/if}
        </span>
        <button
          type="button"
          class="hp-delete-icon"
          aria-label="Delete highlight"
          title="Delete highlight"
          on:click={() => promptDeleteHighlight(highlight)}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      </div>
      <div class="hp-note-editor-shell" role="presentation" on:pointerdown={() => setPinned?.(true)}>
        <NoteEditor
          placement="popup"
          {autoFocus}
          initialContent={getPrimaryNoteForHighlight(highlightId)?.content ?? ''}
          highlight={backendHighlight ?? null}
          onSave={(draft) => savePopupHighlightNote(highlightId, draft)}
          onStatusChange={(s) => popupNoteStatus = s}
          onClose={() => { popupNoteStatus = 'idle'; setPinned?.(false); }}
        />
      </div>
    </div>
    <div class="hp-divider"></div>
    <div class="hp-section">
      <div class="hp-colors" role="group" aria-label="Highlight colors">
        {#each HIGHLIGHT_COLOR_OPTIONS as option}
          <button
            type="button"
            class="hp-color-dot {getHighlightColorName(backendHighlight ?? null) === option.name ? 'is-active' : ''}"
            aria-label={`Set highlight color to ${option.label}`}
            title={`Set color to ${option.label}`}
            style={`--hp-color: ${option.hex};`}
            on:click={(event) => {
              event.preventDefault();
              event.stopPropagation();
              storeHighlightId && void updateHighlightColor(storeHighlightId, option.name, setPinned);
            }}
          ></button>
        {/each}
      </div>
    </div>
  </div>
{/snippet}

{#snippet highlightPopup(highlight: PopupHighlightLike, setPinned: (flag: boolean) => void)}
  {@render inlineHighlightPopup(highlight, setPinned)}
{/snippet}

{#snippet editHighlightPopup(highlight: PopupHighlightLike)}
  {@render inlineHighlightPopup(highlight, getPopupPinnedSetter(highlight.id ?? ''), true)}
{/snippet}

<svelte:head>
  <title>{documentTitle} — Maktaba Reader</title>
  <style>
    :root {
      --paper-bg: var(--paper);
      --paper-bg-2: var(--paper-2);
      --paper-bg-3: var(--paper-3);
      --accent-soft: var(--accent-soft);
    }

    html,
    body {
      height: 100%;
    }

    body {
      margin: 0;
      background: var(--paper-bg-3);
      color: var(--ink);
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
      background: var(--topbar-bg);
      border-bottom: 1px solid var(--rule);
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
      font-size: 18px;
      font-weight: 500;
      letter-spacing: 0.07em;
      color: var(--ink);
      text-decoration: none;
    }

    .reader-nav { display: flex; gap: 4px; align-items: center; }

    .reader-nav-link {
      font-family: var(--font-serif);
      font-size: 14px;
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
      background: var(--paper-2);
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
      font-size: 13px;
      font-weight: 400;
      color: var(--ink-2);
      letter-spacing: 0.04em;
      white-space: nowrap;
    }
    .tb-progress-track {
      width: 68px;
      height: 2px;
      padding: 0;
      background: var(--paper-3);
      border: 0;
      border-radius: 999px;
      overflow: hidden;
      cursor: pointer;
    }
    .tb-progress-track:disabled { cursor: default; }
    .tb-progress-fill  { display: block; height: 100%; border-radius: inherit; transition: background 0.3s; }
    .tb-progress-fill--reading { background: linear-gradient(90deg, #e11d48, #fb7185); }
    .tb-progress-fill--complete { background: linear-gradient(90deg, #36b37e, #65d19c); }

    .tb-status {
      font-family: var(--font-mono); font-size: 12px; font-weight: 400;
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
      font-family: var(--font-serif); font-size: 13px; font-weight: 300;
      letter-spacing: 0.05em; color: var(--ink-3);
      padding: 5px 9px;
      border: 1px solid var(--rule); border-radius: 8px;
      cursor: pointer; user-select: none;
      background: var(--panel-bg); white-space: nowrap;
      transition: background 0.15s, color 0.15s;
    }
    .tb-summary:hover, .tb-summary.tb-active { background: var(--paper-2); color: var(--ink); }
    .tb-summary.tb-active { border-color: color-mix(in srgb, var(--accent) 38%, var(--rule)); }
    .tb-summary::after { content: '\25BE'; font-size: 11px; margin-left: 2px; }
    .tb-summary::-webkit-details-marker { display: none; }
    .tb-summary--icon {
      justify-content: center;
      width: 34px;
      height: 30px;
      padding: 0;
    }
    .tb-summary--icon::after { margin-left: 0; }

    .tb-dropdown {
      position: absolute; top: calc(100% + 4px); left: 0; z-index: 200;
      min-width: 150px;
      background: var(--panel-bg-strong);
      border: 0.5px solid var(--rule);
      border-radius: 8px;
      box-shadow: var(--shadow-strong);
      backdrop-filter: none;
      padding: 4px 0;
    }
    .tb-dropdown--right { left: auto; right: 0; min-width: 180px; }

    .tb-dropdown-item {
      display: flex; align-items: center; width: 100%;
      padding: 8px 14px;
      font-family: var(--font-mono); font-size: 13px; font-weight: 300;
      letter-spacing: 0.05em; color: var(--ink);
      background: transparent; border: none; text-align: left;
      cursor: pointer; transition: background 0.12s;
    }
    .tb-dropdown-item:hover { background: var(--paper-2); }
    .tb-dropdown-item.tb-active { color: var(--ink); font-weight: 400; background: rgba(184,92,46,0.08); }
    .tb-dropdown-item.tb-active::before { content: '\2713  '; }

    .tb-dropdown-divider { height: 0.5px; background: var(--rule); margin: 4px 0; }
    .tb-dropdown-label {
      padding: 7px 14px 4px;
      font-family: var(--font-mono);
      font-size: 10px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--ink-3);
    }
    .tb-color-dot {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: var(--tb-color);
      border: 1px solid rgba(26,24,20,0.22);
      margin-right: 8px;
      flex-shrink: 0;
    }

    .tb-slider-row { display: flex; align-items: center; gap: 8px; padding: 8px 14px; background: color-mix(in srgb, var(--panel-bg) 78%, transparent); }
    .tb-slider-btn { font-size: 14px; color: var(--ink-3); background: transparent; border: none; cursor: pointer; padding: 0 2px; flex-shrink: 0; line-height: 1; }
    .tb-slider-btn:hover { color: var(--ink); }
    .tb-slider { flex: 1; accent-color: var(--accent); }

    /* ── Reading position navigation ──────────────── */
    .tb-nav { display: flex; align-items: center; border: 1px solid var(--rule); border-radius: 8px; overflow: hidden; background: var(--panel-bg); }
    .tb-nav-btn {
      font-family: var(--font-mono); font-size: 13px; color: var(--ink-3);
      background: transparent; border: none; padding: 5px 9px; cursor: pointer;
      transition: background 0.12s, color 0.12s; line-height: 1;
    }
    .tb-nav-btn:first-child { border-right: 0.5px solid var(--rule); }
    .tb-nav-btn:last-child  { border-left:  0.5px solid var(--rule); }
    .tb-nav-btn:hover:not(:disabled) { background: var(--paper-2); color: var(--ink); }
    .tb-nav-btn:disabled { opacity: 0.3; cursor: default; }
    .tb-nav-page {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 9px;
      font-size: 11px;
    }
    .tb-nav-percent { color: var(--ink-3); }
    .tb-nav-progress { margin-left: 2px; }

    .tb-page-input {
      width: 3.2ch;
      min-width: 28px;
      padding: 2px 0;
      border: 0;
      border-bottom: 1px solid transparent;
      background: transparent;
      color: var(--ink);
      font-family: var(--font-mono);
      font-size: 12px;
      text-align: center;
      outline: none;
    }
    .tb-page-input:focus {
      border-bottom-color: var(--accent);
    }
    .tb-page-total { color: var(--ink-3); }

    /* ── Link buttons ────────────────── */
    .tb-link {
      font-family: var(--font-serif); font-size: 13px; font-weight: 300;
      letter-spacing: 0.05em; color: var(--ink-3);
      text-decoration: none; padding: 5px 9px;
      border: 1px solid var(--rule); border-radius: 8px;
      background: var(--panel-bg);
      white-space: nowrap; transition: background 0.15s, color 0.15s;
    }
    .tb-link:hover { background: var(--paper-2); color: var(--ink); }
    .tb-link--icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 30px;
      height: 30px;
      padding: 0;
      font-size: 14px;
    }

    .sr-only {
      position: absolute; width: 1px; height: 1px;
      padding: 0; margin: -1px; overflow: hidden;
      clip: rect(0,0,0,0); border: 0;
    }

    /* ── Highlight popup ──────────────────────── */
    .Highlight__popup.hp-popup {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: stretch !important;
      gap: 12px;
      min-width: 320px;
      max-width: 440px;
      background: var(--panel-bg-strong) !important;
      background-color: var(--panel-bg-strong) !important;
      color: var(--ink) !important;
      border: 0.5px solid var(--rule) !important;
      border-radius: 10px;
      box-shadow: var(--shadow-strong) !important;
      padding: 18px 22px 22px !important;
      overflow-x: hidden;
    }
    .hp-section {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
      width: 100%;
    }
    .hp-section--actions { gap: 10px; }
    .hp-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .hp-delete-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 26px;
      height: 26px;
      padding: 0;
      background: transparent;
      border: none;
      color: #be123c;
      cursor: pointer;
      border-radius: 6px;
      transition: background 0.12s, color 0.12s;
    }
    .hp-delete-icon:hover { background: rgba(244,63,94,.12); color: #991b1b; }
    .hp-label-group { display: inline-flex; align-items: center; gap: 8px; }
    .hp-save-dot { display: inline-block; width: 10px; height: 10px; border-radius: 999px; }
    .hp-save-dot--saving { background: linear-gradient(90deg,#f59e0b,#fb923c); animation: hp-pulse 1s ease-in-out infinite; }
    .hp-save-dot--saved { background: #16a34a; }
    .hp-save-dot--error { background: #be123c; }
    @keyframes hp-pulse { 0%{ transform: scale(1); opacity: 1 } 50%{ transform: scale(1.35); opacity: .65 } 100%{ transform: scale(1); opacity: 1 } }
    .hp-divider {
      height: 1px;
      background: var(--rule);
      margin: 0;
    }
    .hp-label {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 300;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--ink-3);
      margin: 0;
    }
    .hp-note-editor-shell {
      width: 100%;
    }
    .hp-colors {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin: 0;
      width: 100%;
    }
    .hp-color-dot {
      width: 16px;
      height: 16px;
      border-radius: 999px;
      border: 1px solid rgba(26,24,20,0.2);
      background: var(--hp-color);
      cursor: pointer;
      transition: transform 0.12s, border-color 0.12s;
    }
    .hp-color-dot:hover {
      transform: translateY(-1px);
      border-color: rgba(26,24,20,0.45);
    }
    .hp-color-dot.is-active {
      border-color: rgba(26,24,20,0.7);
      box-shadow: 0 0 0 1px rgba(26,24,20,0.3);
    }
    .hp-note-preview {
      align-self: stretch;
      font-family: var(--font-serif);
      font-size: 15px;
      font-weight: 400;
      color: var(--ink-2);
      text-align: left;
      border-left: 1.5px solid var(--accent-soft);
      padding-left: 10px;
      margin: 0;
      line-height: 1.65;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .hp-action-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-family: var(--font-mono);
      font-size: 13px;
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
      padding: 0;
      background: var(--paper-bg);
    }

    .reader-meta {
      display: none;
    }

    .reader-kicker {
      margin: 0 0 10px;
      font-family: var(--font-serif);
      font-size: 13px;
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
      border: none !important;
      border-radius: 0 !important;
      box-shadow: none !important;
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
      box-shadow: inset 1px 0 0 color-mix(in srgb, var(--ink) 8%, transparent) !important;
      background: var(--paper-bg) !important;
    }

    .reader-sidebar-tabs {
      display: flex;
      gap: 12px;
      padding: 0 14px;
      border-bottom: 1px solid var(--rule);
      background: var(--panel-bg-strong);
      flex-shrink: 0;
    }

    .reader-sidebar .reader-sidebar-tab {
      position: relative;
      padding: 12px 2px 10px !important;
      border: 0 !important;
      border-bottom: 2px solid transparent !important;
      border-radius: 0 !important;
      background: transparent !important;
      font-family: var(--font-serif) !important;
      font-size: 13px;
      font-weight: 400;
      letter-spacing: 0.09em;
      color: var(--ink-2) !important;
      text-transform: lowercase;
      cursor: pointer;
      opacity: 0.8;
    }

    .reader-sidebar .reader-sidebar-tabs .reader-sidebar-tab.active {
      color: var(--accent) !important;
      border-color: transparent !important;
      border-bottom: 2px solid var(--accent) !important;
      opacity: 1;
    }

    .reader-sidebar-search {
      padding: 10px 16px;
      border-bottom: 1px solid var(--rule);
      background: var(--panel-bg-strong);
      flex-shrink: 0;
    }

    .reader-sidebar-search input {
      width: 100%;
      border: 1px solid var(--rule);
      border-radius: 7px;
      padding: 7px 10px;
      background: var(--panel-bg);
      color: var(--ink);
      font-family: var(--font-serif);
      font-size: 13px;
      outline: none;
    }

    .reader-sidebar-search input::placeholder {
      color: var(--ink-3);
    }

    .reader-sidebar-tools {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px 10px;
      border-bottom: 1px solid var(--rule);
      background: var(--panel-bg-strong);
      flex-shrink: 0;
    }

    .reader-sidebar-tools-label {
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 400;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--ink-3);
      margin-right: 2px;
    }

    .reader-sidebar-tools button {
      border: 1px solid var(--rule) !important;
      background: var(--panel-bg) !important;
      color: var(--ink-3) !important;
      border-radius: 6px !important;
      padding: 4px 8px !important;
      font-family: var(--font-serif) !important;
      font-size: 12px !important;
      font-weight: 300 !important;
      letter-spacing: 0.06em !important;
      cursor: pointer;
    }

    .reader-sidebar-tools button.active {
      color: var(--ink) !important;
      border-color: var(--accent) !important;
      background: var(--accent-soft) !important;
    }

    .reader-sidebar > section {
      margin: 0 !important;
      border: 0 !important;
      border-bottom: 1px solid var(--rule) !important;
      border-radius: 0 !important;
      background: var(--panel-bg-strong) !important;
      box-shadow: none !important;
      padding: 14px 18px 16px !important;
    }

    .reader-highlights-panel .grid.grid-cols-2 button,
    .reader-navigation-panel button,
    .reader-stage .reader-topbar-actions a,
    .reader-sidebar .reader-sidebar-tab {
      font-family: var(--font-serif) !important;
      font-size: 14px !important;
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
      font-size: 14px !important;
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
      font-size: 14px !important;
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
      font-size: 14px !important;
      font-weight: 300;
      color: var(--ink) !important;
      white-space: normal;
      line-height: 1.65;
    }

    .reader-sidebar [data-testid='notes-sidebar'] li > button:first-child .rounded-full {
      background: transparent !important;
      padding: 0 !important;
      font-family: var(--font-serif);
      font-size: 12px !important;
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

    .reader-sidebar .rounded-2xl {
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
      padding: 10px 14px 6px;
      flex-shrink: 0;
    }

    .paper-sidebar-section-label {
      font-family: var(--font-mono);
      font-size: 12px;
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
      font-size: 13px;
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
      font-size: 13px;
      font-weight: 300;
      color: var(--ink-2);
      padding: 4px 0;
      border-bottom: 0.5px solid var(--rule);
    }
    .paper-highlight-item:last-child { border-bottom: 0; }
    .paper-highlight-item > span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .paper-hl-note-btn {
      font-family: var(--font-mono);
      font-size: 12px;
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
      font-size: 12px;
      color: var(--ink-3);
      background: transparent;
      border: none;
      cursor: pointer;
      padding: 2px 4px;
      flex-shrink: 0;
    }
    .paper-hl-del-btn:hover { color: #c44040; }

    .paper-add-note-btn {
      font-size: 12px !important;
      padding: 3px 8px !important;
    }

    .paper-note-group-label {
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 400;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--ink-2);
      padding: 10px 14px 5px;
      margin: 0;
    }

    .paper-note-item {
      border-bottom: 1px solid var(--rule);
      border-top: 1px solid color-mix(in srgb, var(--ink) 6%, transparent);
      padding: 10px 14px;
      background: var(--panel-bg);
      transition: background 0.12s, box-shadow 0.12s;
    }
    .paper-note-item:hover { background: var(--paper); }

    .paper-annotation-card {
      cursor: pointer;
    }

    .paper-annotation-card:focus-visible {
      outline: 2px solid rgb(166 79 37 / 0.45);
      outline-offset: -2px;
    }

    .paper-document-note-card {
      background: color-mix(in srgb, var(--paper-2) 72%, transparent);
    }

    .paper-note-loc {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-bottom: 6px;
    }

    .paper-note-label {
      font-family: var(--font-mono);
      font-size: 12px;
      font-weight: 400;
      letter-spacing: 0.08em;
      color: var(--ink-2);
    }

    .paper-note-quote {
      font-size: 13px;
      font-style: italic;
      color: var(--ink-2);
      border-left: 3px solid var(--note-quote-color, var(--accent));
      padding-left: 8px;
      margin-bottom: 6px;
      line-height: 1.45;
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
      font-size: 13px;
      font-weight: 400;
      line-height: 1.5;
      color: var(--ink);
    }

    .paper-note-body-btn--static {
      cursor: pointer;
    }

    .paper-note-del {
      font-size: 13px;
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
        padding: 0;
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
      <div class="tb-nav" aria-label="Reading position">
        <button class="tb-nav-btn" type="button" disabled={currentPage <= 1} on:click={goToPreviousPage} aria-label="Previous page">‹</button>
        <span class="tb-label tb-nav-page">

          <input
            class="tb-page-input"
            type="text"
            inputmode="numeric"
            aria-label="Go to page"
            bind:value={pageJumpDraft}
            on:focus={() => { pageJumpFocused = true; }}
            on:blur={() => { pageJumpFocused = false; commitPageJump(); }}
            on:keydown={handlePageJumpKeydown}
          />
          <span class="tb-page-total">/ {totalPages || '—'}</span>
          <span class="sr-only">{currentPage} / {totalPages || '—'}</span>
          <span class="tb-nav-percent">· {readingProgressPercent}%</span>
          <button
            class="tb-progress-track tb-nav-progress"
            type="button"
            disabled={!totalPages}
            on:click={handleReadingProgressClick}
            aria-label="Jump by reading progress"
          >
            <span class="tb-progress-fill" class:tb-progress-fill--reading={!readingProgressComplete} class:tb-progress-fill--complete={readingProgressComplete} style={`width:${readingProgressPercent}%`}></span>
          </button>
        </span>
        <button class="tb-nav-btn" type="button" disabled={currentPage >= totalPages} on:click={goToNextPage} aria-label="Next page">›</button>
      </div>
      {#if jobStatus !== 'ready'}
        <span class="tb-status tb-status--{jobStatus}">{jobStatusLabel}</span>
      {/if}
    </div>

    <div class="reader-topbar-right">
      <!-- sr-only for tests -->
      <span class="sr-only">
        {#if highlightMode === 'text'}Select text directly in the PDF to save a highlight.{:else if highlightMode === 'draw'}Click and drag over the PDF to draw a highlight box.{:else}Highlighting is off.{/if}
      </span>

      <!-- Highlight dropdown -->
      <details class="tb-menu">
        <summary class="tb-summary tb-summary--icon" class:tb-active={highlightMode !== 'off'} aria-label="Highlight tools" title={highlightMode === 'off' ? 'Highlight tools: off' : `Highlight tools: ${highlightMode}`}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 17 4 4 11-11-4-4L3 17z"/><path d="m14 6 2-2 4 4-2 2"/><path d="M3 21h10"/></svg>
          <span class="sr-only">Highlight tools</span>
        </summary>
        <div class="tb-dropdown tb-dropdown--right">
          <div class="tb-dropdown-label">Mode</div>
          <button type="button" class="tb-dropdown-item" class:tb-active={highlightMode === 'off'} on:click={() => setHighlightMode('off')}>Off / read</button>
          <button type="button" class="tb-dropdown-item" class:tb-active={highlightMode === 'text'} on:click={() => setHighlightMode('text')}>Select text</button>
          <button type="button" class="tb-dropdown-item" class:tb-active={highlightMode === 'draw'} on:click={() => setHighlightMode('draw')}>Draw box</button>
          <div class="tb-dropdown-divider"></div>
          <div class="tb-dropdown-label">Color</div>
          {#each HIGHLIGHT_COLOR_OPTIONS as option, index}
            <button
              type="button"
              class="tb-dropdown-item"
              class:tb-active={getCurrentColorIndex() === index}
              on:click={() => setSelectedHighlightColor(index)}
            >
              <span class="tb-color-dot" style={`--tb-color: ${option.hex};`}></span>
              {option.label}
            </button>
          {/each}
        </div>
      </details>

      <!-- Zoom dropdown -->
      <details class="tb-menu">
        <summary class="tb-summary tb-summary--icon" aria-label={`Zoom: ${zoomDisplay}`} title={`Zoom: ${zoomDisplay}`}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg>
          <span class="sr-only">Zoom: {zoomDisplay}</span>
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

      <a class="tb-link tb-link--icon" href={data.fileUrl} target="_blank" rel="noreferrer" aria-label="Open PDF in a new tab" title="Open PDF">↗</a>
    </div>
  </header>

  <div class="reader-workspace">
    <aside class="reader-sidebar paper-sidebar">
      <div class="paper-sidebar-tabs reader-sidebar-tabs" role="tablist" aria-label="Sidebar sections">
        <button
          type="button"
          class="reader-sidebar-tab"
          class:active={sidebarMode === 'annotations'}
          role="tab"
          aria-selected={sidebarMode === 'annotations'}
          on:click={() => { sidebarMode = 'annotations'; }}
        >highlights</button>
        <button
          type="button"
          class="reader-sidebar-tab"
          class:active={sidebarMode === 'document-notes'}
          role="tab"
          aria-selected={sidebarMode === 'document-notes'}
          on:click={() => { sidebarMode = 'document-notes'; }}
        >notes</button>
      </div>

      <div class="paper-search reader-sidebar-search">
        <input
          type="search"
          bind:value={sidebarSearchQuery}
          placeholder={sidebarMode === 'annotations' ? 'search annotations…' : 'search document notes…'}
          aria-label={sidebarMode === 'annotations' ? 'Search annotations' : 'Search document notes'}
        />
      </div>

      <section data-testid="notes-sidebar" class="reader-notes-panel">
        <div class="paper-notes-header">
          <p class="paper-sidebar-section-label">{sidebarMode === 'annotations' ? 'Annotations' : 'Document notes'}</p>
          {#if sidebarMode === 'document-notes'}
            <button
              type="button"
              class="paper-btn-accent paper-add-note-btn"
              on:click={() => void openDocumentNoteEditor()}
            >
              Add note
            </button>
          {/if}
        </div>

        {#if sidebarMode === 'document-notes' && activeNoteTarget?.kind === 'document'}
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
        {:else if sidebarMode === 'annotations' && activeNoteTarget?.kind === 'highlight' && noteEditorPlacement === 'sidebar'}
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
          <p class="text-xs text-slate-500">Loading {sidebarMode === 'annotations' ? 'annotations' : 'document notes'}…</p>
        {:else if notesError}
          <p class="text-xs text-rose-300">{notesError}</p>
        {:else if sidebarMode === 'annotations'}
          {#if filteredHighlightSidebarGroups.length === 0}
            <p class="paper-sidebar-empty">{normalizeSidebarSearch(sidebarSearchQuery) ? 'No annotations match your search.' : 'No annotations yet.'}</p>
          {:else}
            {#each filteredHighlightSidebarGroups as group (group.pageNumber)}
              <p class="paper-note-group-label">Page {group.pageNumber}</p>
              {#each group.highlights as highlight (highlight.id)}
                {@const highlightNote = getPrimaryNoteForHighlight(highlight.id)}
                <div
                  class="paper-note-item paper-annotation-card"
                  role="button"
                  tabindex="0"
                  on:click={() => void handleSidebarHighlightClick(highlight)}
                  on:keydown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      void handleSidebarHighlightClick(highlight);
                    }
                  }}
                >
                  <div class="paper-note-quote" style={`--note-quote-color: ${getHighlightColorHex(highlight)};`}>&ldquo;{highlight.extracted_text || '(no text extracted)'}&rdquo;</div>
                  <div class="paper-note-body-row">
                    <div class="paper-note-body-btn paper-note-body-btn--static">
                      <div class="paper-note-body">{highlightNote?.content || 'No note yet.'}</div>
                    </div>
                    <button
                      type="button"
                      class="paper-hl-note-btn"
                      aria-label={highlightNote ? 'Edit highlight note' : 'Add highlight note'}
                      on:click={(event) => {
                        event.stopPropagation();
                        void openHighlightNoteEditor(highlight.id, undefined, 'sidebar');
                      }}
                    >
                      note
                    </button>
                    <button
                      type="button"
                      class="paper-note-del"
                      aria-label="Delete highlight"
                      on:click={(event) => {
                        event.stopPropagation();
                        promptDeleteHighlight(highlight);
                      }}
                    >✕</button>
                  </div>
                </div>
              {/each}
            {/each}
          {/if}
        {:else if filteredDocumentNotes.length === 0}
          <p class="paper-sidebar-empty">{normalizeSidebarSearch(sidebarSearchQuery) ? 'No document notes match your search.' : 'No document notes yet.'}</p>
        {:else}
          {#each filteredDocumentNotes as note (note.id)}
            <div class="paper-note-item paper-document-note-card">
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
      </section>

    </aside>

    <section class="reader-stage">
      <div class="reader-meta">
        <p class="reader-kicker">PDF reader</p>
        <h1 class="reader-title">{documentTitle}</h1>
        <p class="reader-authors">{authorsLabel}</p>
      </div>

      <div class="reader-stage-card">
        <div class="reader-stage-body">
        <div bind:this={pdfViewerHostEl} class="reader-pdf-shell relative h-full overflow-hidden">
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
                  <div class="flex h-full items-center justify-center text-sm" style="color: var(--ink-3);">
                    Loading PDF… {progress.total ? Math.floor((progress.loaded / progress.total) * 100) : 0}%
                  </div>
                {/snippet}

                {#snippet errorMessage(loadError)}
                  <div class="flex h-full items-center justify-center p-6">
                    <div class="max-w-lg rounded-2xl border p-6 text-sm" style="border-color: rgba(190, 18, 60, 0.35); background: rgba(254, 242, 242, 0.9); color: #991b1b;">
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
                    style="width: 100%; height: 100%; background: var(--paper-bg); scrollbar-width: thin; scrollbar-color: rgba(22,19,15,0.25) transparent;"
                  />
                {/snippet}
              </PdfLoader>
            {/if}
          {:else}
            <div class="flex h-full items-center justify-center p-6 text-sm" style="color: var(--ink-3);">
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
    background: var(--paper-bg-3);
    overflow-anchor: none;
  }

  :global(.reader-pdf-shell .pdfViewer) {
    overflow-anchor: none;
  }

  :global(.reader-pdf-shell .pdfViewer .page) {
    margin: 0 auto;
    background: var(--paper-bg);
    box-shadow: var(--shadow-strong);
    overflow-anchor: none;
  }

  :global(html[data-theme='dark'] .reader-pdf-shell canvas) {
    filter: invert(0.91) hue-rotate(180deg) brightness(0.92) contrast(0.94);
  }

  /* thin modern scrollbar */
  :global(.reader-pdf-shell .PdfHighlighter) { scrollbar-width: thin; scrollbar-color: color-mix(in srgb, var(--ink) 28%, transparent) transparent; }
  :global(.reader-pdf-shell .PdfHighlighter::-webkit-scrollbar) { width: 7px; height: 7px; }
  :global(.reader-pdf-shell .PdfHighlighter::-webkit-scrollbar-track) { background: transparent; }
  :global(.reader-pdf-shell .PdfHighlighter::-webkit-scrollbar-thumb) { background: color-mix(in srgb, var(--ink) 28%, transparent); border-radius: 3px; }
  :global(.reader-pdf-shell .PdfHighlighter::-webkit-scrollbar-thumb:hover) { background: color-mix(in srgb, var(--ink) 45%, transparent); }
  :global(.reader-pdf-shell .PdfHighlighter::-webkit-scrollbar-corner) { background: transparent; }
</style>
