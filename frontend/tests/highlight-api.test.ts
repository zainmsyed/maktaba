import { describe, expect, it } from 'vitest';

import {
  backendToLibraryHighlight,
  buildCreatePayload,
  type BackendHighlight,
  type LibraryHighlight,
} from '../src/routes/library/[documentId]/highlight-api';

describe('highlight-api helpers', () => {
  it('maps backend highlights into the library format', () => {
    const backendHighlight: BackendHighlight = {
      id: 'highlight-1',
      page_number: 3,
      x: 0.1,
      y: 0.2,
      width: 0.3,
      height: 0.4,
      extracted_text: 'Hello highlight',
    };

    const libraryHighlight = backendToLibraryHighlight(backendHighlight);

    expect(libraryHighlight).toMatchObject({
      id: 'highlight-1',
      type: 'area',
      content: { text: 'Hello highlight' },
      color_index: 0,
      serverPersisted: true,
    });
    expect(libraryHighlight.position?.boundingRect).toMatchObject({
      pageNumber: 3,
      x1: 0.1,
      y1: 0.2,
      x2: 0.4,
      y2: 0.6000000000000001,
      width: 1,
      height: 1,
    });
  });

  it('builds a normalized create payload from a library highlight', () => {
    const highlight = {
      id: 'temp-highlight',
      type: 'area',
      content: { text: '  Selected text  ' },
      position: {
        boundingRect: {
          x1: 100,
          y1: 120,
          x2: 240,
          y2: 150,
          width: 800,
          height: 1000,
          pageNumber: 1,
        },
        rects: [],
      },
    } as LibraryHighlight;

    expect(buildCreatePayload(highlight)).toEqual({
      page_number: 1,
      x: 0.125,
      y: 0.12,
      width: 0.175,
      height: 0.03,
      extracted_text: 'Selected text',
    });
  });
});
