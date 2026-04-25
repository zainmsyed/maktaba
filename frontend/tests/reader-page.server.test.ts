import { describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({
  env: {
    PUBLIC_API_URL: 'http://public.test',
  },
}));

vi.mock('$env/dynamic/private', () => ({
  env: {
    SERVER_API_URL: 'http://backend.test',
  },
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
    },
  });
}

describe('reader page server load', () => {
  it('fetches the library from the server api url and returns browser-facing urls', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        documents: [
          {
            document: {
              id: 'doc-1',
              title: 'Reader Test',
              authors: ['Ada Lovelace'],
              format: 'pdf',
              page_count: 3,
            },
            jobs: [{ status: 'pending', job_type: 'extract_text' }],
          },
        ],
      }),
    );

    const { load } = await import('../src/routes/library/[documentId]/+page.server');
    const result = await load({
      fetch: fetchMock as typeof fetch,
      params: { documentId: 'doc-1' },
    } as never);

    expect(fetchMock).toHaveBeenCalledWith('http://backend.test/api/documents');
    expect(result.apiUrl).toBe('http://public.test');
    expect(result.fileUrl).toBe('http://public.test/api/documents/doc-1/file');
    expect(result.document.id).toBe('doc-1');
    expect(result.jobs).toHaveLength(1);
  });
});
