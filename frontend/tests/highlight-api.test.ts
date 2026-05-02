import { describe, expect, it } from 'vitest';

import {
  backendToLibraryHighlight,
  buildCreatePayload,
  type BackendHighlight,
  type LibraryHighlight,
} from '../src/routes/library/[documentId]/highlight-api';

describe('highlight-api helpers', () => {
  it('maps legacy backend highlights into the area format', () => {
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
    expect(libraryHighlight.position?.rects).toEqual([]);
  });

  it('maps persisted text highlights back to line rects instead of one area box', () => {
    const backendHighlight: BackendHighlight = {
      id: 'highlight-2',
      color: 'green',
      highlight_type: 'text',
      page_number: 7,
      x: 0.1,
      y: 0.2,
      width: 0.6,
      height: 0.08,
      extracted_text: 'A two line highlight',
      rects: [
        { x1: 0.1, y1: 0.2, x2: 0.7, y2: 0.23, width: 1, height: 1, pageNumber: 7 },
        { x1: 0.1, y1: 0.25, x2: 0.55, y2: 0.28, width: 1, height: 1, pageNumber: 7 },
      ],
    };

    const libraryHighlight = backendToLibraryHighlight(backendHighlight);

    expect(libraryHighlight.type).toBe('text');
    expect(libraryHighlight.color_index).toBe(1);
    expect(libraryHighlight.position?.rects).toEqual(backendHighlight.rects);
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
      highlight_type: 'area',
      rects: [],
    });
  });

  it('preserves normalized rect geometry for text highlights', () => {
    const highlight = {
      id: 'temp-highlight',
      type: 'text',
      content: { text: 'Selected text' },
      position: {
        boundingRect: {
          x1: 80,
          y1: 100,
          x2: 480,
          y2: 180,
          width: 800,
          height: 1000,
          pageNumber: 2,
        },
        rects: [
          { x1: 80, y1: 100, x2: 480, y2: 130, width: 800, height: 1000, pageNumber: 2 },
          { x1: 80, y1: 150, x2: 300, y2: 180, width: 800, height: 1000, pageNumber: 2 },
        ],
      },
    } as LibraryHighlight;

    expect(buildCreatePayload(highlight)).toMatchObject({
      page_number: 2,
      x: 0.1,
      y: 0.1,
      width: 0.5,
      height: 0.08,
      extracted_text: 'Selected text',
      highlight_type: 'text',
      rects: [
        { x1: 0.1, y1: 0.1, x2: 0.6, y2: 0.13, width: 1, height: 1, pageNumber: 2 },
        { x1: 0.1, y1: 0.15, x2: 0.375, y2: 0.18, width: 1, height: 1, pageNumber: 2 },
      ],
    });
  });
});
