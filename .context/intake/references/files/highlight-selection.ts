/**
 * Maktaba PDF Highlight Selection — drop-in replacement
 *
 * Replace the following in +page.svelte:
 *   - all selection state variables (selecting, selStart, selRect, etc.)
 *   - commitTextSelection / queueTextSelectionCommit
 *   - addGlobalSelectionListeners / removeGlobalSelectionListeners
 *   - onTextLayerMouseUp (if you have one)
 *
 * Keep: createHighlight(), deleteHighlightById(), loadHighlights(),
 *        getHighlightStyle(), onHighlightClick(), draw-mode pointer handlers,
 *        and all PDF rendering code.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * HOW IT WORKS
 * ─────────────────────────────────────────────────────────────────────────────
 * Instead of relying on window.getSelection() / range.getBoundingClientRect()
 * (broken for Arabic RTL transformed spans), we:
 *
 *   1. On mousedown over the textLayerEl, record which span was hit (startIdx).
 *   2. On mousemove, find the span under the pointer and record endIdx.
 *      Visually highlight the spanned divs with a live preview overlay.
 *   3. On mouseup, union the BoundingClientRects of all spanned spans
 *      (relative to viewerEl), normalize to 0–1, POST to FastAPI.
 *
 * getBoundingClientRect() on individual span *elements* is reliable even for
 * RTL/transformed content — it's only the Range API that breaks.
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─── STATE (add these to your let declarations) ───────────────────────────────

// Replace your existing selection state block with:
//
//   let hlSelecting = false;
//   let hlStartIdx = -1;
//   let hlEndIdx = -1;
//   let hlPreviewRects: Array<{left:number;top:number;width:number;height:number}> = [];
//   let hlTextDivs: HTMLElement[] = [];   // populated after each TextLayer render

// ─── CALL THIS after textLayer.render() completes ────────────────────────────

export function syncTextDivs(textLayerEl: HTMLElement): HTMLElement[] {
  // TextLayer renders spans directly into the container.
  // We grab them in DOM order — that is reading order for LTR;
  // for RTL/Arabic, DOM order still gives us a consistent index space.
  return Array.from(textLayerEl.querySelectorAll('span[role="presentation"]')) as HTMLElement[];
}

// ─── HIT TEST: which span index is under a pointer position ──────────────────

function spanIndexAt(
  textDivs: HTMLElement[],
  clientX: number,
  clientY: number
): number {
  // elementFromPoint gives us the exact span even through transforms
  const el = document.elementFromPoint(clientX, clientY);
  if (!el) return -1;
  const idx = textDivs.indexOf(el as HTMLElement);
  if (idx !== -1) return idx;
  // Sometimes the hit is on a child node inside the span
  const parent = (el as HTMLElement).closest?.('span[role="presentation"]');
  if (parent) return textDivs.indexOf(parent as HTMLElement);
  return -1;
}

// ─── COMPUTE PREVIEW RECTS from a span index range ───────────────────────────

export function computePreviewRects(
  textDivs: HTMLElement[],
  startIdx: number,
  endIdx: number,
  viewerEl: HTMLElement
): Array<{ left: number; top: number; width: number; height: number }> {
  if (startIdx < 0 || endIdx < 0 || textDivs.length === 0) return [];

  const lo = Math.min(startIdx, endIdx);
  const hi = Math.max(startIdx, endIdx);
  const viewerRect = viewerEl.getBoundingClientRect();
  const rects: Array<{ left: number; top: number; width: number; height: number }> = [];

  for (let i = lo; i <= hi; i++) {
    const span = textDivs[i];
    if (!span) continue;
    const r = span.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    rects.push({
      left: r.left - viewerRect.left,
      top: r.top - viewerRect.top,
      width: r.width,
      height: r.height,
    });
  }

  return rects;
}

// ─── COMPUTE NORMALIZED BOUNDING BOX (for DB storage) ────────────────────────
// We store a single bounding rect (your existing DB schema: x, y, width, height)
// as the union of all selected span rects, normalized 0–1 relative to the viewer.

export function computeNormalizedBounds(
  previewRects: Array<{ left: number; top: number; width: number; height: number }>,
  pageDisplaySize: { width: number; height: number }
): { x: number; y: number; width: number; height: number } | null {
  if (previewRects.length === 0) return null;
  const { width: pw, height: ph } = pageDisplaySize;
  if (pw <= 0 || ph <= 0) return null;

  let minLeft = Infinity, minTop = Infinity, maxRight = -Infinity, maxBottom = -Infinity;
  for (const r of previewRects) {
    minLeft = Math.min(minLeft, r.left);
    minTop = Math.min(minTop, r.top);
    maxRight = Math.max(maxRight, r.left + r.width);
    maxBottom = Math.max(maxBottom, r.top + r.height);
  }

  return {
    x: Math.max(0, minLeft / pw),
    y: Math.max(0, minTop / ph),
    width: Math.min(1, (maxRight - minLeft) / pw),
    height: Math.min(1, (maxBottom - minTop) / ph),
  };
}

// ─── EXTRACT TEXT from selected spans ────────────────────────────────────────

export function extractSelectedText(
  textDivs: HTMLElement[],
  startIdx: number,
  endIdx: number
): string {
  const lo = Math.min(startIdx, endIdx);
  const hi = Math.max(startIdx, endIdx);
  return textDivs
    .slice(lo, hi + 1)
    .map((s) => s.textContent ?? '')
    .join(' ')
    .trim();
}

// ─── THE THREE EVENT HANDLERS (bind these to textLayerEl in your markup) ─────
//
// Usage in Svelte markup:
//
//   <div
//     bind:this={textLayerEl}
//     data-testid="pdf-text-layer-host"
//     class="absolute inset-0 z-10 textLayer"
//     style="--total-scale-factor: {currentScale}"
//     on:mousedown={onTextLayerMouseDown}
//     on:mousemove={onTextLayerMouseMove}
//     on:mouseup={onTextLayerMouseUp}
//   ></div>

export function makeSelectionHandlers(deps: {
  getMode: () => 'text' | 'draw';
  getTextDivs: () => HTMLElement[];
  getViewerEl: () => HTMLElement | null;
  getPageDisplaySize: () => { width: number; height: number };
  getCurrentPage: () => number;
  onCommit: (payload: {
    page_number: number;
    x: number; y: number;
    width: number; height: number;
    extracted_text: string;
  }) => void;
  setPreviewRects: (rects: Array<{ left: number; top: number; width: number; height: number }>) => void;
}) {
  let selecting = false;
  let startIdx = -1;
  let endIdx = -1;

  function onMouseDown(e: MouseEvent) {
    if (deps.getMode() !== 'text') return;
    // Only left button
    if (e.button !== 0) return;

    const idx = spanIndexAt(deps.getTextDivs(), e.clientX, e.clientY);
    if (idx === -1) return;

    selecting = true;
    startIdx = idx;
    endIdx = idx;
    deps.setPreviewRects([]);
    // Prevent browser from starting its own selection (the source of bugs)
    e.preventDefault();
  }

  function onMouseMove(e: MouseEvent) {
    if (!selecting || deps.getMode() !== 'text') return;

    const idx = spanIndexAt(deps.getTextDivs(), e.clientX, e.clientY);
    if (idx === -1) return;
    endIdx = idx;

    const viewerEl = deps.getViewerEl();
    if (!viewerEl) return;

    const rects = computePreviewRects(deps.getTextDivs(), startIdx, endIdx, viewerEl);
    deps.setPreviewRects(rects);
  }

  function onMouseUp(e: MouseEvent) {
    if (!selecting || deps.getMode() !== 'text') return;
    selecting = false;

    const viewerEl = deps.getViewerEl();
    if (!viewerEl) { deps.setPreviewRects([]); return; }

    const finalIdx = spanIndexAt(deps.getTextDivs(), e.clientX, e.clientY);
    if (finalIdx !== -1) endIdx = finalIdx;

    const rects = computePreviewRects(deps.getTextDivs(), startIdx, endIdx, viewerEl);
    const bounds = computeNormalizedBounds(rects, deps.getPageDisplaySize());
    const text = extractSelectedText(deps.getTextDivs(), startIdx, endIdx);

    deps.setPreviewRects([]); // clear live preview

    if (!bounds || text.length === 0 || bounds.width < 0.005 || bounds.height < 0.005) return;

    deps.onCommit({
      page_number: deps.getCurrentPage(),
      extracted_text: text,
      ...bounds,
    });

    startIdx = -1;
    endIdx = -1;
  }

  return { onMouseDown, onMouseMove, onMouseUp };
}
