import type { Highlight } from 'svelte-pdf-highlighter';

type BackendHighlightRect = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  height: number;
  pageNumber: number;
};

export type BackendHighlightColor = 'yellow' | 'green' | 'blue' | 'red';

const BACKEND_HIGHLIGHT_COLORS: BackendHighlightColor[] = ['yellow', 'green', 'blue', 'red'];

function colorNameToIndex(color: string | null | undefined): number {
  const normalized = (color || '').toLowerCase();
  const found = BACKEND_HIGHLIGHT_COLORS.indexOf(normalized as BackendHighlightColor);
  return found >= 0 ? found : 0;
}

export type BackendHighlight = {
  id: string;
  format?: string | null;
  highlight_type?: 'text' | 'area' | null;
  color?: BackendHighlightColor | null;
  extracted_text?: string | null;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  rects?: BackendHighlightRect[] | null;
  created_at?: string;
  updated_at?: string;
};

export type BackendNote = {
  id: string;
  document_id: string;
  highlight_id?: string | null;
  content: string;
  page_number?: number | null;
  highlight?: BackendHighlight | null;
  created_at?: string;
  updated_at?: string;
};

export type LibraryHighlight = Highlight & {
  serverPersisted?: boolean;
};

export type HighlightCreatePayload = {
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  extracted_text?: string;
  highlight_type?: 'text' | 'area';
  rects?: BackendHighlightRect[];
  color?: BackendHighlightColor;
};

type HighlightUpdatePayload = {
  color?: BackendHighlightColor;
};

type NoteCreatePayload = {
  content: string;
  highlight_id?: string | null;
};

type NoteUpdatePayload = {
  content: string;
};

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

async function parseJsonOrThrow<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) {
    const txt = await response.text();
    throw new Error(`${message}: ${response.status} ${txt}`);
  }
  return response.json() as Promise<T>;
}

async function expectOk(response: Response, message: string): Promise<void> {
  if (!response.ok) {
    const txt = await response.text();
    throw new Error(`${message}: ${response.status} ${txt}`);
  }
}

function normalizeRect(rect: BackendHighlightRect, fallbackPageNumber: number): BackendHighlightRect {
  const baseWidth = rect.width || 1;
  const baseHeight = rect.height || 1;
  const x1 = Math.min(rect.x1, rect.x2) / baseWidth;
  const y1 = Math.min(rect.y1, rect.y2) / baseHeight;
  const x2 = Math.max(rect.x1, rect.x2) / baseWidth;
  const y2 = Math.max(rect.y1, rect.y2) / baseHeight;

  return {
    x1: clamp01(x1),
    y1: clamp01(y1),
    x2: clamp01(x2),
    y2: clamp01(y2),
    width: 1,
    height: 1,
    pageNumber: rect.pageNumber ?? fallbackPageNumber,
  };
}

function denormalizeRect(rect: BackendHighlightRect, fallbackPageNumber: number): BackendHighlightRect {
  return {
    x1: rect.x1,
    y1: rect.y1,
    x2: rect.x2,
    y2: rect.y2,
    width: rect.width || 1,
    height: rect.height || 1,
    pageNumber: rect.pageNumber ?? fallbackPageNumber,
  };
}

export function backendToLibraryHighlight(highlight: BackendHighlight): LibraryHighlight {
  const boundingRect = {
    x1: highlight.x,
    y1: highlight.y,
    x2: highlight.x + highlight.width,
    y2: highlight.y + highlight.height,
    width: 1,
    height: 1,
    pageNumber: highlight.page_number,
  };
  const rects = (highlight.rects ?? []).map((rect) => denormalizeRect(rect, highlight.page_number));
  const type = highlight.highlight_type === 'text' && rects.length > 0 ? 'text' : 'area';

  return {
    id: highlight.id,
    type,
    content: highlight.extracted_text ? { text: highlight.extracted_text } : {},
    position: {
      boundingRect,
      rects: type === 'text' ? rects : [],
    },
    color_index: colorNameToIndex(highlight.color),
    serverPersisted: true,
  };
}

export function buildCreatePayload(highlight: LibraryHighlight): HighlightCreatePayload | null {
  const boundingRect = highlight.position?.boundingRect;
  if (!boundingRect) return null;

  const baseWidth = boundingRect.width || 1;
  const baseHeight = boundingRect.height || 1;
  const x1 = Math.min(boundingRect.x1, boundingRect.x2);
  const y1 = Math.min(boundingRect.y1, boundingRect.y2);
  const x2 = Math.max(boundingRect.x1, boundingRect.x2);
  const y2 = Math.max(boundingRect.y1, boundingRect.y2);
  const width = (x2 - x1) / baseWidth;
  const height = (y2 - y1) / baseHeight;

  if (width < 0.005 || height < 0.005) return null;

  const pageNumber = boundingRect.pageNumber;
  const rects = (highlight.position?.rects ?? []).map((rect) => normalizeRect(rect, pageNumber));
  const highlightType = highlight.type === 'text' && rects.length > 0 ? 'text' : 'area';

  return {
    page_number: pageNumber,
    x: clamp01(x1 / baseWidth),
    y: clamp01(y1 / baseHeight),
    width: clamp01(width),
    height: clamp01(height),
    extracted_text: highlight.content?.text?.trim() ?? '',
    highlight_type: highlightType,
    rects,
  };
}

export function createHighlightClient(apiUrl: string, documentId: string) {
  const highlightCollectionUrl = `${apiUrl}/api/documents/${documentId}/highlights`;
  const highlightUrl = (highlightId: string) => `${apiUrl}/api/highlights/${highlightId}`;

  return {
    async fetchHighlights(): Promise<BackendHighlight[]> {
      const payload = await parseJsonOrThrow<{ highlights?: BackendHighlight[] }>(
        await fetch(highlightCollectionUrl),
        'Failed to load highlights',
      );
      return payload.highlights || [];
    },

    async createHighlight(payload: HighlightCreatePayload): Promise<BackendHighlight> {
      const resp = await fetch(highlightCollectionUrl, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          format: 'pdf',
          color: payload.color ?? 'yellow',
          extracted_text: payload.extracted_text ?? '',
          highlight_type: payload.highlight_type ?? 'area',
          rects: payload.rects ?? [],
          page_number: payload.page_number,
          x: payload.x,
          y: payload.y,
          width: payload.width,
          height: payload.height,
        }),
      });

      const json = await parseJsonOrThrow<{ highlight: BackendHighlight }>(
        resp,
        'Failed to create highlight',
      );
      return json.highlight;
    },

    async updateHighlight(highlightId: string, payload: HighlightUpdatePayload): Promise<BackendHighlight> {
      const resp = await fetch(highlightUrl(highlightId), {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          color: payload.color,
        }),
      });

      const json = await parseJsonOrThrow<{ highlight: BackendHighlight }>(
        resp,
        'Failed to update highlight',
      );
      return json.highlight;
    },

    async deleteHighlight(highlightId: string): Promise<void> {
      await expectOk(
        await fetch(highlightUrl(highlightId), { method: 'DELETE' }),
        'Failed to delete highlight',
      );
    },
  };
}

export function createNoteClient(apiUrl: string, documentId: string) {
  const notesCollectionUrl = `${apiUrl}/api/documents/${documentId}/notes`;
  const noteUrl = (noteId: string) => `${apiUrl}/api/notes/${noteId}`;

  return {
    async fetchNotes(): Promise<BackendNote[]> {
      const payload = await parseJsonOrThrow<{ notes?: BackendNote[] }>(
        await fetch(notesCollectionUrl),
        'Failed to load notes',
      );
      return payload.notes || [];
    },

    async createNote(payload: NoteCreatePayload): Promise<BackendNote> {
      const resp = await fetch(notesCollectionUrl, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          content: payload.content,
          highlight_id: payload.highlight_id ?? null,
        }),
      });

      const json = await parseJsonOrThrow<{ note: BackendNote }>(resp, 'Failed to create note');
      return json.note;
    },

    async updateNote(noteId: string, payload: NoteUpdatePayload): Promise<BackendNote> {
      const resp = await fetch(noteUrl(noteId), {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          content: payload.content,
        }),
      });

      const json = await parseJsonOrThrow<{ note: BackendNote }>(resp, 'Failed to update note');
      return json.note;
    },

    async deleteNote(noteId: string): Promise<void> {
      await expectOk(await fetch(noteUrl(noteId), { method: 'DELETE' }), 'Failed to delete note');
    },
  };
}
