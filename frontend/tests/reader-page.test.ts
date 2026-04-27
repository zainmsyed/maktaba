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

    deleteHighlight = (highlight: T) => {
      this.highlights = this.highlights.filter((item) => item.id !== highlight.id);
      this.emit();
    };
  }

  return {
    PdfLoader,
    PdfHighlighter,
    HighlightsModel,
  };
});

import ReaderPage from '../src/routes/library/[documentId]/+page.svelte';

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
  fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (init?.method === 'POST' && url.includes('/highlights')) {
      const payload = JSON.parse(String(init.body || '{}'));
      return jsonResponse({
        highlight: {
          id: 'highlight-1',
          page_number: payload.page_number,
          x: payload.x,
          y: payload.y,
          width: payload.width,
          height: payload.height,
          extracted_text: payload.extracted_text,
          color: payload.color,
          format: payload.format,
        },
      });
    }

    if (init?.method === 'DELETE' && url.includes('/api/highlights/')) {
      return jsonResponse({ deleted: true });
    }

    return jsonResponse({ highlights: [] });
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
      expect(getByText('Processing')).toBeTruthy();
    });

    await fireEvent.click(getByRole('button', { name: 'Fit page' }));

    await waitFor(() => {
      expect(getByRole('button', { name: 'Fit page' })).toBeTruthy();
    });

    await fireEvent.click(getByRole('button', { name: 'Next' }));

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
      expect(getByText('Highlights')).toBeTruthy();
      expect(getByRole('button', { name: 'Select text' })).toBeTruthy();
      expect(getByRole('button', { name: 'Draw box' })).toBeTruthy();
      expect(getByText(/Select text directly in the PDF/i)).toBeTruthy();
      expect(getByText('No highlights on this page.')).toBeTruthy();
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
      const postCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
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
      });
    });
  });
});
