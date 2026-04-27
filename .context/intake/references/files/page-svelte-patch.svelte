<!-- ============================================================
     MAKTABA — PDF HIGHLIGHT SELECTION PATCH
     Apply these changes to +page.svelte
     ============================================================ -->


<!-- ── 1. IMPORTS (top of <script>) ──────────────────────────── -->

<script lang="ts">
  import { makeSelectionHandlers, syncTextDivs, computePreviewRects } from './highlight-selection';
  // ... your existing imports


  <!-- ── 2. REPLACE selection state variables ─────────────────── -->

  // REMOVE these:
  //   let selecting = false;
  //   let selStart = { x: 0, y: 0 };
  //   let selRect = { left: 0, top: 0, width: 0, height: 0 };
  //   let activePointerId ...
  //   let overlayPointerTarget ...
  //   let selectionFrame ...

  // ADD these instead:
  let hlTextDivs: HTMLElement[] = [];
  let hlPreviewRects: Array<{ left: number; top: number; width: number; height: number }> = [];

  const { onMouseDown: onTextMouseDown, onMouseMove: onTextMouseMove, onMouseUp: onTextMouseUp } =
    makeSelectionHandlers({
      getMode: () => highlightMode,
      getTextDivs: () => hlTextDivs,
      getViewerEl: () => viewerEl,
      getPageDisplaySize: () => pageDisplaySize,
      getCurrentPage: () => currentPage,
      setPreviewRects: (r) => { hlPreviewRects = r; },
      onCommit: (payload) => {
        // your existing createHighlight() — it already accepts this shape
        void createHighlight(payload);
      },
    });


  <!-- ── 3. AFTER textLayer.render() — sync the divs ─────────── -->

  // Inside your renderTextLayer function, after `await textLayer.render()`:
  //
  //   hlTextDivs = syncTextDivs(textLayerEl!);
  //   console.log('[textlayer] synced divs:', hlTextDivs.length);
  //
  // Also clear them when the page changes:
  //   hlTextDivs = [];
  //   hlPreviewRects = [];


  <!-- ── 4. REMOVE these functions entirely ───────────────────── -->
  // commitTextSelection()
  // queueTextSelectionCommit()
  // addGlobalSelectionListeners()
  // removeGlobalSelectionListeners()
  // selectionBelongsToTextLayer()
  // (keep all draw-mode pointer handlers — those are fine)


  <!-- ── 5. UPDATE createHighlight() to send extracted_text ───── -->
  // Your existing createHighlight() takes { page_number, x, y, width, height }
  // Add extracted_text to the type and body:

  async function createHighlight(payload: {
    page_number: number;
    x: number; y: number;
    width: number; height: number;
    extracted_text?: string;   // ← add this
  }) {
    if (creatingHighlight) return;
    creatingHighlight = true;
    try {
      const resp = await fetch(`${data.apiUrl}/api/documents/${data.document.id}/highlights`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          format: 'pdf',               // ← required by your DB constraint
          color: 'yellow',             // ← required by your DB constraint
          extracted_text: payload.extracted_text ?? '',
          page_number: payload.page_number,
          x: payload.x,
          y: payload.y,
          width: payload.width,
          height: payload.height,
        }),
      });
      if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
      const json = await resp.json();
      highlights = [...highlights, json.highlight];
    } catch (e) {
      console.error('[highlight] create error', e);
    } finally {
      creatingHighlight = false;
    }
  }
</script>


<!-- ── 6. MARKUP: text layer host ───────────────────────────── -->

<!--
  REMOVE: on:mouseup={queueTextSelectionCommit}
  ADD: the three new handlers
  REMOVE: overflow-hidden  ← this was breaking drag selection
-->
<div
  bind:this={textLayerEl}
  data-testid="pdf-text-layer-host"
  role="presentation"
  class="absolute inset-0 z-10 rounded-lg textLayer"
  style="--total-scale-factor: {currentScale}"
  on:mousedown={onTextMouseDown}
  on:mousemove={onTextMouseMove}
  on:mouseup={onTextMouseUp}
></div>


<!-- ── 7. MARKUP: live preview overlay ──────────────────────── -->

<!--
  Add this ABOVE the text layer div (lower z-index so it doesn't block mouse):
  z-index 5 = below text layer (z-10), above canvas (z-0)
-->
<div class="absolute inset-0 z-5 pointer-events-none">
  <!-- Live selection preview while dragging -->
  {#each hlPreviewRects as r}
    <div
      class="absolute"
      style="
        left: {r.left}px;
        top: {r.top}px;
        width: {r.width}px;
        height: {r.height}px;
        background: rgba(253, 224, 71, 0.45);
        mix-blend-mode: multiply;
        border-radius: 1px;
      "
    />
  {/each}

  <!-- Persisted highlights for current page -->
  {#each currentPageHighlights as h}
    <div
      class="absolute cursor-pointer"
      style="{getHighlightStyle(h)} background: rgba(253, 224, 71, 0.35); mix-blend-mode: multiply; border-radius: 1px;"
      role="button"
      tabindex="0"
      on:click={() => onHighlightClick(h)}
      on:keydown={(e) => e.key === 'Enter' && onHighlightClick(h)}
    />
  {/each}
</div>


<!-- ── 8. STYLE: prevent browser text selection cursor fighting ── -->

<style>
  /* Tell the browser not to do its own text selection — we handle it */
  :global([data-testid="pdf-text-layer-host"]) {
    user-select: none !important;
    -webkit-user-select: none !important;
    cursor: text;
  }
  :global([data-testid="pdf-text-layer-host"] span) {
    cursor: text;
  }
</style>


<!--
  ── WHY THIS WORKS ────────────────────────────────────────────────────────────

  Old approach problems:
  1. selectionchange fires constantly, committing partial drags as highlights
  2. range.getBoundingClientRect() returns wrong rects for RTL/transformed spans
  3. overflow-hidden clips the browser's internal selection drag tracking
  4. Browser selection and your custom highlight competed for the same events

  New approach:
  1. We preventDefault() on mousedown → browser never starts its own selection
  2. We use document.elementFromPoint() to hit-test spans — works perfectly
     through CSS transforms, RTL reordering, and scaled viewports
  3. Preview rects come from span.getBoundingClientRect() — reliable for elements
  4. The final stored rect is the union bounding box of selected spans, normalized
     0–1 so it survives zoom/resize changes (your getHighlightStyle already handles this)
  5. extracted_text is the concatenated textContent of selected spans — clean

  ─────────────────────────────────────────────────────────────────────────────
-->
