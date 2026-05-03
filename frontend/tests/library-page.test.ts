import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const gotoMock = vi.hoisted(() => vi.fn());

vi.mock('$app/navigation', () => ({
  goto: gotoMock,
}));
import { advanceAndFlush } from './test-helpers';
import LibraryPage from '../src/routes/library/+page.svelte';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
    },
  });
}

describe('library page', () => {
  beforeEach(() => {
    gotoMock.mockClear();
  });
  it('re-sorts cards when the sort mode changes', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        documents: [
          {
            document: {
              id: 'doc-z',
              title: 'Zulu',
              authors: ['Zed'],
              format: 'pdf',
              created_at: '2024-01-02T10:00:00Z',
              updated_at: '2024-01-02T10:00:00Z',
              reading_progress: {},
            },
            jobs: [],
          },
          {
            document: {
              id: 'doc-a',
              title: 'Alpha',
              authors: ['Ada'],
              format: 'pdf',
              created_at: '2024-01-01T10:00:00Z',
              updated_at: '2024-01-01T10:00:00Z',
              reading_progress: {},
            },
            jobs: [],
          },
        ],
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    const { getAllByRole, getByLabelText } = render(LibraryPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
        },
      },
    });

    await waitFor(() => {
      const titles = getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent);
      expect(titles).toEqual(['Zulu', 'Alpha']);
    });

    await fireEvent.change(getByLabelText('Sort'), {
      target: { value: 'title' },
    });

    await waitFor(() => {
      const titles = getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent);
      expect(titles).toEqual(['Alpha', 'Zulu']);
    });
  });

  it('navigates highlight search results with an explicit highlight target', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [] }))
      .mockResolvedValue(jsonResponse({
        results: [{
          id: 'highlight-1',
          source_type: 'highlight',
          document_id: 'doc-1',
          document_title: 'Global Search Doc',
          page_number: 2,
          content: 'matching highlight',
          highlight_id: null,
        }],
      }));

    vi.stubGlobal('fetch', fetchMock);

    const { getByLabelText, getAllByRole } = render(LibraryPage, {
      props: { data: { apiUrl: 'http://api.test' } },
    });

    await advanceAndFlush(0);
    await fireEvent.input(getByLabelText('Search notes and highlights'), { target: { value: 'matching' } });
    await advanceAndFlush(250);
    await fireEvent.click(getAllByRole('option')[0]);

    expect(gotoMock).toHaveBeenCalledWith('/library/doc-1?highlight=highlight-1');
  });

  it('navigates note search results with a page target', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [] }))
      .mockResolvedValue(jsonResponse({
        results: [{
          id: 'note-1',
          source_type: 'note',
          document_id: 'doc-2',
          document_title: 'Global Search Doc 2',
          page_number: 5,
          content: 'matching note',
          highlight_id: null,
        }],
      }));

    vi.stubGlobal('fetch', fetchMock);

    const { getByLabelText, getAllByRole } = render(LibraryPage, {
      props: { data: { apiUrl: 'http://api.test' } },
    });

    await advanceAndFlush(0);
    await fireEvent.input(getByLabelText('Search notes and highlights'), { target: { value: 'matching' } });
    await advanceAndFlush(250);
    await fireEvent.click(getAllByRole('option')[0]);

    expect(gotoMock).toHaveBeenCalledWith('/library/doc-2?page=5');
  });

  it('replaces the optimistic upload card with the server response', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ documents: [] }))
      .mockResolvedValueOnce(
        jsonResponse({
          created: true,
          document: {
            id: 'doc-1',
            title: 'Server Title',
            authors: ['Ada Lovelace'],
            format: 'pdf',
            created_at: '2024-02-01T10:00:00Z',
            updated_at: '2024-02-01T10:00:00Z',
            reading_progress: {},
            file_hash: 'abc123',
          },
          jobs: [
            {
              id: 'job-1',
              job_type: 'extract_text',
              status: 'pending',
              payload: {
                document_id: 'doc-1',
                file_hash: 'abc123',
                format: 'pdf',
                title: 'Server Title',
                authors: ['Ada Lovelace'],
                page_count: 1,
              },
            },
          ],
        }),
      );

    vi.stubGlobal('fetch', fetchMock);

    const { container, getAllByRole, queryByText, getByText } = render(LibraryPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
        },
      },
    });

    await waitFor(() => {
      expect(getByText('No documents yet - upload a PDF or EPUB to get started.')).toBeTruthy();
    });

    const fileInput = container.querySelector('input[type="file"]');
    expect(fileInput).not.toBeNull();

    const file = new File(['hello world'], 'draft.pdf', { type: 'application/pdf' });
    await fireEvent.change(fileInput as HTMLInputElement, {
      target: {
        files: [file],
      },
    });

    await waitFor(() => {
      const titles = getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent);
      expect(titles).toContain('draft');
    });

    await waitFor(() => {
      const titles = getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent);
      expect(titles).toContain('Server Title');
    });

    expect(queryByText('draft')).toBeNull();
  });

  it('keeps the delete button right-aligned when a card has no stats', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse({
        documents: [
          {
            document: {
              id: 'doc-no-stats',
              title: 'No Stats',
              authors: ['Anonymous'],
              format: 'pdf',
              created_at: '2024-01-01T10:00:00Z',
              updated_at: '2024-01-01T10:00:00Z',
              reading_progress: {},
            },
            jobs: [],
            highlight_count: 0,
            note_count: 0,
          },
        ],
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    const { container } = render(LibraryPage, {
      props: { data: { apiUrl: 'http://api.test' } },
    });

    await waitFor(() => {
      const deleteBtn = container.querySelector('.delete-btn');
      expect(deleteBtn).toBeTruthy();
      expect(deleteBtn?.classList.contains('push-right')).toBe(true);
    });
  });

  it('polls for job updates until processing documents become ready', async () => {
    vi.useFakeTimers();

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(
        jsonResponse({
          documents: [
            {
              document: {
                id: 'doc-1',
                title: 'Pollable Document',
                authors: ['Ada Lovelace'],
                format: 'pdf',
                created_at: '2024-02-01T10:00:00Z',
                updated_at: '2024-02-01T10:00:00Z',
                reading_progress: {},
              },
              jobs: [
                {
                  id: 'job-1',
                  job_type: 'extract_text',
                  status: 'pending',
                  payload: {
                    document_id: 'doc-1',
                    file_hash: 'abc123',
                    format: 'pdf',
                    title: 'Pollable Document',
                    authors: ['Ada Lovelace'],
                    page_count: 10,
                  },
                },
              ],
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          documents: [
            {
              document: {
                id: 'doc-1',
                title: 'Pollable Document',
                authors: ['Ada Lovelace'],
                format: 'pdf',
                created_at: '2024-02-01T10:00:00Z',
                updated_at: '2024-02-01T10:00:00Z',
                reading_progress: {},
              },
              jobs: [
                {
                  id: 'job-1',
                  job_type: 'extract_text',
                  status: 'completed',
                  payload: {
                    document_id: 'doc-1',
                    file_hash: 'abc123',
                    format: 'pdf',
                    title: 'Pollable Document',
                    authors: ['Ada Lovelace'],
                    page_count: 10,
                  },
                },
              ],
            },
          ],
        }),
      );

    vi.stubGlobal('fetch', fetchMock);

    const { getByText } = render(LibraryPage, {
      props: {
        data: {
          apiUrl: 'http://api.test',
        },
      },
    });

    await advanceAndFlush(0);

    expect(getByText('Extracting…')).toBeTruthy();

    await advanceAndFlush(5000);

    expect(getByText('Open to read')).toBeTruthy();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
