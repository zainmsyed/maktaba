import { env as publicEnv } from '$env/dynamic/public';
import { env as privateEnv } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';

interface LibraryDocument {
  id: string;
  title?: string | null;
  authors?: string[];
  format?: string;
  created_at?: string;
  updated_at?: string;
  reading_progress?: Record<string, unknown>;
}

interface LibraryEntry {
  document: LibraryDocument;
  jobs?: unknown[];
}

export const load = async ({ fetch, params }) => {
  // client-facing API URL (used in links returned to the browser)
  const clientApiUrl = (publicEnv.PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
  // server-side URL to use when fetching from inside the frontend container. Falls back to clientApiUrl.
  const serverApiUrl = (privateEnv.SERVER_API_URL || clientApiUrl).replace(/\/$/, '');

  const response = await fetch(`${serverApiUrl}/api/documents`);
  if (!response.ok) {
    throw error(response.status, 'Unable to load the library');
  }

  const payload: { documents?: LibraryEntry[] } = await response.json();
  const selected = (payload.documents || []).find((entry) => entry.document?.id === params.documentId);

  if (!selected) {
    throw error(404, 'Document not found');
  }

  if ((selected.document?.format || '').toLowerCase() !== 'pdf') {
    throw error(415, 'The reader currently supports PDF documents only');
  }

  return {
    apiUrl: clientApiUrl,
    document: selected.document,
    jobs: selected.jobs ?? [],
    fileUrl: `${clientApiUrl}/api/documents/${params.documentId}/file`,
  };
};
