import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ReaderPage from '../src/routes/library/[documentId]/+page.svelte';

const pdfjsMocks = vi.hoisted(() => {
  const renderTask = { promise: Promise.resolve(), cancel: vi.fn() };
  const fakePage = {
    getViewport: ({ scale }: { scale: number }) => ({ width: 800 * scale, height: 1000 * scale }),
    render: vi.fn(() => renderTask),
  };
  const fakeDocument = {
    numPages: 3,
    getPage: vi.fn().mockResolvedValue(fakePage),
    destroy: vi.fn(),
  };

  return {
    renderTask,
    fakePage,
    fakeDocument,
    getDocument: vi.fn(() => ({ promise: Promise.resolve(fakeDocument) })),
  };
});

vi.mock('pdfjs-dist/build/pdf.mjs', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: pdfjsMocks.getDocument,
}));

vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({
  default: '/pdf.worker.min.mjs',
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('reader page', () => {
  it('loads the reader shell and renders page 1 on mount', async () => {
    const { getByText, getByRole, getAllByText } = render(ReaderPage, {
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
      expect(pdfjsMocks.getDocument).toHaveBeenCalledWith({ url: 'http://api.test/api/documents/doc-1/file' });
      expect(pdfjsMocks.fakeDocument.getPage).toHaveBeenCalledWith(1);
      expect(pdfjsMocks.fakePage.render).toHaveBeenCalledTimes(1);
      expect(getByText('Showing page 1 of 3')).toBeTruthy();
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

  it('shows the highlights panel with drag instructions', async () => {
    const { getByText } = render(ReaderPage, {
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
      expect(getByText(/Click and drag over the PDF/i)).toBeTruthy();
      expect(getByText('No highlights on this page.')).toBeTruthy();
    });
  });
});
