import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('svelte-pdf-highlighter', async () => {
  const { default: PdfLoader } = await import('./mocks/MockPdfLoader.svelte');
  const { default: PdfHighlighter } = await import('./mocks/MockPdfHighlighter.svelte');

  class HighlightsModel<T extends Record<string, any>> {
    highlights: T[];
    listeners = new Set<(arr: Array<T>) => unknown>();

    constructor(highlights: Array<T> = []) {
      this.highlights = highlights;
    }

    subscribe = (callback: (arr: Array<T>) => unknown) => {
      this.listeners.add(callback);
      return () => this.listeners.delete(callback);
    };

    private emit() {
      for (const listener of this.listeners) {
        listener(this.highlights);
      }
    }

    addHighlight = (highlight: T) => {
      const next = { ...highlight, id: highlight.id ?? `mock-${this.highlights.length + 1}` } as T;
      this.highlights = [...this.highlights, next];
      this.emit();
      return next;
    };

    editHighlight = (highlightId: string, changes: Partial<T>) => {
      this.highlights = this.highlights.map((item) =>
        item.id === highlightId ? ({ ...item, ...changes } as T) : item,
      );
      this.emit();
    };

    deleteHighlight = (highlight: T) => {
      this.highlights = this.highlights.filter((item) => item.id !== highlight.id);
      this.emit();
    };

    getHighlightById = (highlightId: string) => this.highlights.find((item) => item.id === highlightId);
  }

  return {
    PdfLoader,
    PdfHighlighter,
    HighlightsModel,
  };
});

import ReaderPage from '../src/routes/library/[documentId]/+page.svelte';
import { advanceAndFlush } from './test-helpers';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
    },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  window.history.pushState({}, '', '/library/doc-1');
  vi.stubGlobal('alert', vi.fn());

  const highlightRecords = new Map<string, any>();
  const noteRecords = new Map<string, any>();

  fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? 'GET';

    if (method === 'POST' && url.includes('/highlights')) {
      const payload = JSON.parse(String(init?.body || '{}'));
      const highlight = {
        id: `highlight-${highlightRecords.size + 1}`,
        page_number: payload.page_number,
        x: payload.x,
        y: payload.y,
        width: payload.width,
        height: payload.height,
        extracted_text: payload.extracted_text,
        highlight_type: payload.highlight_type,
        rects: payload.rects,
        color: payload.color,
        format: payload.format,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      highlightRecords.set(highlight.id, highlight);
      return jsonResponse({ highlight });
    }

    if (method === 'PATCH' && /\/api\/highlights\/[^/]+$/.test(url)) {
      const highlightId = url.split('/').pop() ?? '';
      const existing = highlightRecords.get(highlightId);
      if (!existing) {
        return jsonResponse({ detail: 'Highlight not found' }, 404);
      }

      const payload = JSON.parse(String(init?.body || '{}'));
      const nextHighlight = {
        ...existing,
        color: payload.color ?? existing.color,
        updated_at: new Date().toISOString(),
      };
      highlightRecords.set(highlightId, nextHighlight);
      return jsonResponse({ highlight: nextHighlight });
    }

    if (method === 'GET' && /\/api\/documents\/[^/]+\/highlights$/.test(url)) {
      return jsonResponse({ highlights: [...highlightRecords.values()] });
    }

    if (method === 'GET' && /\/api\/documents\/[^/]+\/notes$/.test(url)) {
      return jsonResponse({ notes: [...noteRecords.values()] });
    }

    if (method === 'POST' && /\/api\/documents\/[^/]+\/notes$/.test(url)) {
      const payload = JSON.parse(String(init?.body || '{}'));
      const documentId = url.match(/\/api\/documents\/([^/]+)\/notes$/)?.[1] ?? 'doc-1';
      const highlight = payload.highlight_id ? highlightRecords.get(payload.highlight_id) ?? null : null;
      const note = {
        id: `note-${noteRecords.size + 1}`,
        document_id: documentId,
        highlight_id: payload.highlight_id ?? null,
        content: payload.content ?? '',
        page_number: highlight?.page_number ?? null,
        highlight: highlight ? { ...highlight } : null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      noteRecords.set(note.id, note);
      return jsonResponse({ note }, 201);
    }

    if (method === 'PATCH' && /\/api\/notes\/[^/]+$/.test(url)) {
      const noteId = url.split('/').pop() ?? '';
      const existing = noteRecords.get(noteId);
      if (!existing) {
        return jsonResponse({ detail: 'Note not found' }, 404);
      }

      const payload = JSON.parse(String(init?.body || '{}'));
      const note = {
        ...existing,
        content: payload.content ?? existing.content,
        updated_at: new Date().toISOString(),
      };
      noteRecords.set(noteId, note);
      return jsonResponse({ note });
    }

    if (method === 'DELETE' && url.includes('/api/highlights/')) {
      const highlightId = url.split('/').pop() ?? '';
      highlightRecords.delete(highlightId);
      for (const [noteId, note] of noteRecords.entries()) {
        if (note.highlight_id === highlightId) {
          noteRecords.delete(noteId);
        }
      }
      return jsonResponse({ deleted: true });
    }

    return jsonResponse({ highlights: [], notes: [] });
  });

  vi.stubGlobal('fetch', fetchMock);
});

describe('reader page', () => {
  it('loads the reader shell and renders page 1 on mount', async () => {
    const { getByText, getByRole, getAllByText, getByTestId } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Reader Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [{ status: 'pending', job_type: 'extract_text' }],
        },
      },
    });

    await waitFor(() => {
      expect(getByTestId('pdf-viewer')).toBeTruthy();
      expect(getAllByText('1 / 3').length).toBeGreaterThan(0);
      expect(getByRole('button', { name: 'Fit width' })).toBeTruthy();
    });

    await fireEvent.click(getByRole('button', { name: 'Fit page' }));

    await waitFor(() => {
      expect(getByRole('button', { name: 'Fit page' })).toBeTruthy();
    });

    await fireEvent.click(getByRole('button', { name: /next page/i }));

    await waitFor(() => {
      expect(getAllByText('2 / 3').length).toBeGreaterThan(0);
    });
  });

  it('shows the highlights panel with both text and draw modes', async () => {
    const { getByText, getByRole, getAllByText } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Highlight Panel Test',
            authors: [],
            format: 'pdf',
            page_count: 1,
          },
          jobs: [],
        },
      },
    });

    await waitFor(() => {
      expect(getByRole('tab', { name: 'highlights' })).toBeTruthy();
      expect(getByRole('button', { name: 'Off / read' })).toBeTruthy();
      expect(getByRole('button', { name: 'Select text' })).toBeTruthy();
      expect(getByRole('button', { name: 'Draw box' })).toBeTruthy();
      expect(getByText(/Highlighting is off/i)).toBeTruthy();
      expect(getByText('No annotations yet.')).toBeTruthy();
    });

    await fireEvent.click(getByRole('button', { name: 'Select text' }));

    await waitFor(() => {
      expect(getByText(/Select text directly in the PDF/i)).toBeTruthy();
    });

    await fireEvent.click(getByRole('button', { name: 'Draw box' }));

    await waitFor(() => {
      expect(getByRole('button', { name: 'Draw box' })).toBeTruthy();
      expect(getAllByText(/Click and drag over the PDF/i).length).toBeGreaterThan(0);
    });
  });

  it('creates a highlight from a text selection', async () => {
    const { getByTestId } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Selection Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 1,
          },
          jobs: [],
        },
      },
    });

    const viewer = await waitFor(() => getByTestId('pdf-viewer'));
    expect(viewer).toBeTruthy();

    const textLayerHost = await waitFor(() => getByTestId('pdf-text-layer-host'));
    await fireEvent.mouseUp(textLayerHost);

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([input, init]) => init?.method === 'POST' && String(input).includes('/highlights'));
      expect(postCall).toBeTruthy();
      expect(JSON.parse(String(postCall?.[1]?.body))).toMatchObject({
        format: 'pdf',
        color: 'yellow',
        extracted_text: 'Selectable highlight text',
        page_number: 1,
        x: 0.125,
        y: 0.12,
        width: 0.175,
        height: 0.03,
        highlight_type: 'text',
        rects: [
          {
            x1: 0.125,
            y1: 0.12,
            x2: 0.3,
            y2: 0.15,
            width: 1,
            height: 1,
            pageNumber: 1,
          },
        ],
      });
    });
  });

  it('updates highlight color from the hover popup palette', async () => {
    const { getByTestId, getByRole } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Highlight Color Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 1,
          },
          jobs: [],
        },
      },
    });

    const textLayerHost = await waitFor(() => getByTestId('pdf-text-layer-host'));
    await fireEvent.mouseUp(textLayerHost);

    const greenButton = await waitFor(() =>
      getByRole('button', { name: /set highlight color to green/i }),
    );
    await fireEvent.click(greenButton);

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([input, init]) => init?.method === 'PATCH' && String(input).includes('/api/highlights/highlight-1'),
      );
      expect(patchCall).toBeTruthy();
      expect(JSON.parse(String(patchCall?.[1]?.body))).toMatchObject({
        color: 'green',
      });
    });
  });

  it('autosaves highlight notes, lists document notes, and jumps from the sidebar', async () => {
    vi.useFakeTimers();
    const scrollIntoViewSpy = vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => undefined);

    const { getByRole, getAllByRole, getByText, getAllByText, getByTestId } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Notes Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    expect(getByTestId('pdf-viewer')).toBeTruthy();
    expect(getByRole('tab', { name: 'highlights' })).toBeTruthy();

    const textLayerHost = getByTestId('pdf-text-layer-host');
    await fireEvent.mouseUp(textLayerHost);
    await advanceAndFlush(0);

    const addHighlightNoteButton = getByRole('button', { name: /add highlight note/i });
    await fireEvent.click(addHighlightNoteButton);
    await advanceAndFlush(0);

    const textarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(textarea, {
      target: {
        value: 'A note about this highlight',
      },
    });

    await advanceAndFlush(500);
    await advanceAndFlush(0);

    expect(getAllByText('Saved').length).toBeGreaterThan(0);
    // The note text appears in the popup editor textarea; verify sidebar shows the page group.
    expect(getByText('Page 1')).toBeTruthy();

    // Click the highlight card in the sidebar to trigger jump/focus
    const sidebar = getByTestId('notes-sidebar');
    const quoteEl = Array.from(sidebar.querySelectorAll('.paper-note-quote')).find(
      (el) => el.textContent?.includes('Selectable highlight text'),
    ) as HTMLElement;
    const highlightSidebarCard = quoteEl?.closest('[role="button"]') as HTMLElement;
    expect(highlightSidebarCard).toBeTruthy();
    await fireEvent.click(highlightSidebarCard);
    expect(scrollIntoViewSpy).toHaveBeenCalled();
    await advanceAndFlush(1200);

    // Switch to the notes tab to add a document note
    const notesTab = getByRole('tab', { name: 'notes' });
    await fireEvent.click(notesTab);
    await advanceAndFlush(0);

    const addNoteButton = getAllByRole('button', { name: 'Add note' }).at(0);
    expect(addNoteButton).toBeTruthy();
    await fireEvent.click(addNoteButton as HTMLElement);
    await advanceAndFlush(0);

    const documentNoteTextarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(documentNoteTextarea, {
      target: {
        value: 'Standalone reflection',
      },
    });

    await advanceAndFlush(500);
    await advanceAndFlush(0);

    await waitFor(() => {
      expect(getByText('Saved')).toBeTruthy();
    });
    await waitFor(() => {
      expect(getByText('Document notes')).toBeTruthy();
      expect(getByText('Standalone reflection')).toBeTruthy();
    });

    const notesSidebar = getByTestId('notes-sidebar');
    const sidebarHeadings = Array.from(notesSidebar.querySelectorAll('p'))
      .filter((el) => el.className.includes('paper-sidebar-section-label') || el.className.includes('paper-note-group-label'))
      .map((el) => el.textContent?.trim())
      .filter((text): text is string => Boolean(text));
    expect(sidebarHeadings).toMatchInlineSnapshot(`
      [
        "Document notes",
      ]
    `);

    const noteCreateCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        init?.method === 'POST' &&
        String(input).includes('/api/documents/doc-1/notes') &&
        String(init?.body || '').includes('Standalone reflection'),
    );
    expect(noteCreateCall).toBeTruthy();
    expect(JSON.parse(String(noteCreateCall?.[1]?.body))).toMatchObject({
      content: 'Standalone reflection',
      highlight_id: null,
    });
  });

  it('applies query highlight jumps instead of restoring saved reading progress', async () => {
    vi.useFakeTimers();
    window.history.pushState({}, '', '/library/doc-1?highlight=highlight-1');
    localStorage.setItem('maktaba:progress:doc-1', JSON.stringify({ lastPage: 3, maxPage: 3, total: 3 }));

    const fetchWithHighlight = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      if (method === 'GET' && /\/api\/documents\/[^/]+\/highlights$/.test(url)) {
        return jsonResponse({
          highlights: [
            {
              id: 'highlight-1',
              page_number: 2,
              x: 10,
              y: 10,
              width: 20,
              height: 10,
              extracted_text: 'query jump highlight',
              highlight_type: 'text',
              rects: [],
              color: 'yellow',
              format: 'pdf',
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          ],
        });
      }
      if (method === 'GET' && /\/api\/documents\/[^/]+\/notes$/.test(url)) {
        return jsonResponse({ notes: [] });
      }
      return jsonResponse({});
    });
    vi.stubGlobal('fetch', fetchWithHighlight);

    const { getAllByText } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Query Jump Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    await advanceAndFlush(32);

    await waitFor(() => {
      expect(getAllByText('2 / 3').length).toBeGreaterThan(0);
    });

    window.history.pushState({}, '', '/library/doc-1');
  });

  it('filters sidebar annotations and document notes from the search box', async () => {
    vi.useFakeTimers();

    const { getByRole, getAllByRole, getByTestId, queryByText } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Search Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    const textLayerHost = getByTestId('pdf-text-layer-host');
    await fireEvent.mouseUp(textLayerHost);
    await advanceAndFlush(0);

    const addHighlightNoteButton = getByRole('button', { name: /add highlight note/i });
    await fireEvent.click(addHighlightNoteButton);
    await advanceAndFlush(0);

    const textarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(textarea, { target: { value: 'alpha note match' } });
    await advanceAndFlush(500);
    await advanceAndFlush(0);

    const annotationSearch = getByRole('searchbox', { name: 'Search annotations' });
    await fireEvent.input(annotationSearch, { target: { value: 'alpha' } });
    await advanceAndFlush(0);
    expect(queryByText('No annotations match your search.')).toBeNull();

    await fireEvent.input(annotationSearch, { target: { value: 'zzz-no-match' } });
    await advanceAndFlush(0);
    expect(queryByText('No annotations match your search.')).toBeTruthy();

    const notesTab = getByRole('tab', { name: 'notes' });
    await fireEvent.click(notesTab);
    await advanceAndFlush(0);

    const addNoteButton = getAllByRole('button', { name: 'Add note' }).at(0) as HTMLElement;
    await fireEvent.click(addNoteButton);
    await advanceAndFlush(0);

    const documentNoteTextarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(documentNoteTextarea, { target: { value: 'standalone reflection' } });
    await advanceAndFlush(500);
    await advanceAndFlush(0);

    const noteSearch = getByRole('searchbox', { name: 'Search document notes' });
    await fireEvent.input(noteSearch, { target: { value: 'reflection' } });
    await advanceAndFlush(0);
    expect(queryByText('No document notes match your search.')).toBeNull();

    await fireEvent.input(noteSearch, { target: { value: 'zzz-no-match' } });
    await advanceAndFlush(0);
    expect(queryByText('No document notes match your search.')).toBeTruthy();
  });

  it('sidebar click focuses highlight and opens the highlight popup/editor', async () => {
    vi.useFakeTimers();
    const { getByRole, getByText, getByTestId } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Notes Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    const textLayerHost = getByTestId('pdf-text-layer-host');
    await fireEvent.mouseUp(textLayerHost);
    await advanceAndFlush(0);

    const addHighlightNoteButton = getByRole('button', { name: /add highlight note/i });
    await fireEvent.click(addHighlightNoteButton);
    await advanceAndFlush(0);

    const textarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(textarea, { target: { value: 'Popup test note' } });
    await advanceAndFlush(500);
    await advanceAndFlush(0);

    // Click the highlight card in the sidebar to trigger jump/focus
    const sidebar = getByTestId('notes-sidebar');
    const quoteEl = Array.from(sidebar.querySelectorAll('.paper-note-quote')).find(
      (el) => el.textContent?.includes('Selectable highlight text'),
    ) as HTMLElement;
    const highlightSidebarCard = quoteEl?.closest('[role="button"]') as HTMLElement;
    expect(highlightSidebarCard).toBeTruthy();
    await fireEvent.click(highlightSidebarCard);

    await waitFor(() => {
      expect(getByTestId('mock-highlight-popup')).toBeTruthy();
    });
  });

  it('autosave shows error on create failure and recovers on retry', async () => {
    vi.useFakeTimers();

    const { getByRole, getByTestId, getByText } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Notes Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    const textLayerHost = getByTestId('pdf-text-layer-host');
    await fireEvent.mouseUp(textLayerHost);
    await advanceAndFlush(0);

    const addHighlightNoteButton = getByRole('button', { name: /add highlight note/i });
    await fireEvent.click(addHighlightNoteButton);
    await advanceAndFlush(0);

    const textarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(textarea, { target: { value: 'Failing note' } });

    // Prepare a one-off implementation that fails the next create note call.
    fetchMock.mockImplementationOnce(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      if (method === 'POST' && /\/api\/documents\/.+\/notes$/.test(url)) {
        return jsonResponse({ detail: 'boom' }, 500);
      }
      return jsonResponse({ highlights: [], notes: [] });
    });

    await advanceAndFlush(500);
    await advanceAndFlush(0);

    // Error state should be shown
    await waitFor(() => {
      expect(getByText('Unable to save note')).toBeTruthy();
    });

    // Now type again and let the next request succeed (original fetchMock will handle it)
    await fireEvent.input(textarea, { target: { value: 'Failing note retry' } });
    await advanceAndFlush(500);
    await advanceAndFlush(0);

    await waitFor(() => {
      expect(getByText('Saved')).toBeTruthy();
    });
  });

  it('switching editors flushes pending draft and deletion closes open editor', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('confirm', vi.fn(() => true));

    const { getByRole, getByTestId, getAllByRole, queryByRole } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Notes Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    const textLayerHost = getByTestId('pdf-text-layer-host');
    await fireEvent.mouseUp(textLayerHost);
    await advanceAndFlush(0);

    const addHighlightNoteButton = getByRole('button', { name: /add highlight note/i });
    await fireEvent.click(addHighlightNoteButton);
    await advanceAndFlush(0);

    const textarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    // Type but do not wait for autosave; switch editors immediately
    await fireEvent.input(textarea, { target: { value: 'Draft to flush' } });

    // Switch to notes tab and click Add note; this should trigger flushActiveNoteDraft
    const notesTab = getByRole('tab', { name: 'notes' });
    await fireEvent.click(notesTab);
    await advanceAndFlush(0);

    const sidebarAddNote = getAllByRole('button', { name: 'Add note' }).at(0);
    expect(sidebarAddNote).toBeTruthy();
    await fireEvent.click(sidebarAddNote as HTMLElement);
    await advanceAndFlush(0);

    // Assert a POST was made to create the pending draft
    const postCall = fetchMock.mock.calls.find(([input, init]) => init?.method === 'POST' && String(input).includes('/api/documents/doc-1/notes') && String(init?.body || '').includes('Draft to flush'));
    expect(postCall).toBeTruthy();

    // Now create a standalone note and ensure deletion closes the editor
    const docTextarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(docTextarea, { target: { value: 'To be deleted' } });
    await advanceAndFlush(500);
    await advanceAndFlush(0);

    // Find the sidebar list item for the created note and click its delete button
    const createdNoteNode = Array.from(document.querySelectorAll('button')).find((el) => el.textContent?.includes('To be deleted')) as HTMLElement | undefined;
    const noteContainer = createdNoteNode?.closest('.paper-note-item, li') as HTMLElement | null;
    const deleteButton = noteContainer?.querySelector('button[aria-label="Delete note"]') as HTMLElement | null;
    if (deleteButton) {
      await fireEvent.click(deleteButton);
      await advanceAndFlush(0);
    }

    // Editor should be closed (no textarea present for active note)
    expect(queryByRole('textbox', { name: 'Note content' })).toBeNull();
  });

  it('saved badge fades after save', async () => {
    vi.useFakeTimers();

    const { getByRole, getByTestId, getByText, getAllByText, queryByText } = render(ReaderPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
          fileUrl: 'http://api.test/api/documents/doc-1/file',
          document: {
            id: 'doc-1',
            title: 'Notes Test',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            page_count: 3,
          },
          jobs: [],
        },
      },
    });

    await advanceAndFlush(0);
    const textLayerHost = getByTestId('pdf-text-layer-host');
    await fireEvent.mouseUp(textLayerHost);
    await advanceAndFlush(0);

    const addHighlightNoteButton = getByRole('button', { name: /add highlight note/i });
    await fireEvent.click(addHighlightNoteButton);
    await advanceAndFlush(0);

    const textarea = await waitFor(() => getByRole('textbox', { name: 'Note content' }));
    await fireEvent.input(textarea, { target: { value: 'Fade test note' } });

    // Allow autosave to run
    await advanceAndFlush(500);
    await advanceAndFlush(0);

    // Should show Saved badge
    expect(getByText('Saved')).toBeTruthy();

    // Advance timers to allow the saved badge to fade (2000ms)
    await advanceAndFlush(2000);
    await advanceAndFlush(0);

    // 'Saved' should no longer be present, replaced by idle message
    expect(queryByText('Saved')).toBeNull();
    const idleMatches = getAllByText(/Start typing to autosave/);
    expect(idleMatches.length).toBeGreaterThan(0);
  });
});
