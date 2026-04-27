import type { Highlight } from 'svelte-pdf-highlighter';

export type BackendHighlight = {
  id: string;
  format?: string | null;
  color?: string | null;
  extracted_text?: string | null;
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
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
};

function clamp01(value: number) {
  return Math.min(1, Math.max(0, value));
}

export function backendToLibraryHighlight(highlight: BackendHighlight): LibraryHighlight {
  return {
    id: highlight.id,
    type: 'area',
    content: highlight.extracted_text ? { text: highlight.extracted_text } : {},
    position: {
      boundingRect: {
        x1: highlight.x,
        y1: highlight.y,
        x2: highlight.x + highlight.width,
        y2: highlight.y + highlight.height,
        width: 1,
        height: 1,
        pageNumber: highlight.page_number,
      },
      rects: [],
    },
    color_index: 0,
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

  return {
    page_number: boundingRect.pageNumber,
    x: clamp01(x1 / baseWidth),
    y: clamp01(y1 / baseHeight),
    width: clamp01(width),
    height: clamp01(height),
    extracted_text: highlight.content?.text?.trim() ?? '',
  };
}

export function createHighlightClient(apiUrl: string, documentId: string) {
  const highlightCollectionUrl = `${apiUrl}/api/documents/${documentId}/highlights`;
  const highlightUrl = (highlightId: string) => `${apiUrl}/api/highlights/${highlightId}`;

  return {
    async fetchHighlights(): Promise<BackendHighlight[]> {
      const resp = await fetch(highlightCollectionUrl);
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`Failed to load highlights: ${resp.status} ${txt}`);
      }
      const payload = await resp.json();
      return (payload.highlights || []) as BackendHighlight[];
    },

    async createHighlight(payload: HighlightCreatePayload): Promise<BackendHighlight> {
      const resp = await fetch(highlightCollectionUrl, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          format: 'pdf',
          color: 'yellow',
          extracted_text: payload.extracted_text ?? '',
          page_number: payload.page_number,
          x: payload.x,
          y: payload.y,
          width: payload.width,
          height: payload.height,
        }),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`Failed to create highlight: ${resp.status} ${txt}`);
      }

      const json = await resp.json();
      return json.highlight as BackendHighlight;
    },

    async deleteHighlight(highlightId: string): Promise<void> {
      const resp = await fetch(highlightUrl(highlightId), { method: 'DELETE' });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`Failed to delete highlight: ${resp.status} ${txt}`);
      }
    },
  };
}
