<script lang="ts">
  import { onMount } from 'svelte';

  let {
    highlightsStore,
    style = '',
    onHighlightsRendered,
    pdfHighlighterUtils = $bindable({}),
    highlightPopup,
    editHighlightPopup,
  }: any = $props();

  let highlights = $state<any[]>([]);
  let activeHighlightId = $state<string | null>(null);
  let pinned = $state(false);

  function setScale(value: unknown) {
    pdfHighlighterUtils = {
      ...pdfHighlighterUtils,
      currentScaleValue: value,
      currentScale: typeof value === 'number' ? value : 1,
    };
  }

  onMount(() => {
    pdfHighlighterUtils = {
      ...pdfHighlighterUtils,
      currentScale: 1,
      currentScaleValue: 'page-width',
      setCurrentScaleValue: (value: unknown) => setScale(value),
    };

    const unsubscribe =
      highlightsStore?.subscribe?.((next: Array<any>) => {
        highlights = [...next];
        const persistedHighlight = [...next].reverse().find((highlight) => highlight.serverPersisted);
        if (!pinned && persistedHighlight) {
          activeHighlightId = persistedHighlight.id;
        } else if (activeHighlightId !== null && !next.some((highlight) => highlight.id === activeHighlightId)) {
          activeHighlightId = null;
        }
      }) ??
      (() => undefined);

    highlights = [...(highlightsStore?.highlights ?? [])];
    activeHighlightId = [...highlights].reverse().find((highlight) => highlight.serverPersisted)?.id ?? null;
    pinned = false;
    onHighlightsRendered?.();

    return () => {
      unsubscribe();
    };
  });

  function createTextHighlight() {
    highlightsStore.addHighlight({
      type: 'text',
      color_index: typeof (pdfHighlighterUtils as any)?.selectedColorIndex === 'number'
        ? (pdfHighlighterUtils as any).selectedColorIndex
        : 0,
      content: { text: 'Selectable highlight text' },
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
        rects: [
          {
            x1: 100,
            y1: 120,
            x2: 240,
            y2: 150,
            width: 800,
            height: 1000,
            pageNumber: 1,
          },
        ],
      },
    });
  }

  function setPinned(flag: boolean) {
    if (flag) {
      pinned = true;
      activeHighlightId = activeHighlightId ?? [...highlights].reverse().find((highlight) => highlight.serverPersisted)?.id ?? highlights.at(-1)?.id ?? null;
      return;
    }

    pinned = false;
    activeHighlightId = null;
  }

  function openHighlight(id: string) {
    pinned = false;
    activeHighlightId = id;
  }
</script>

<div data-testid="pdf-viewer" class="PdfHighlighter" style={style}>
  <div class="page" data-page-number="1">
    <div role="presentation" data-testid="pdf-text-layer-host" onmouseup={createTextHighlight}>Mock text layer</div>
  </div>
  <div class="page" data-page-number="2"></div>
  <div class="page" data-page-number="3"></div>

  <div class="mock-highlight-list">
    {#each highlights as highlight}
      <button
        type="button"
        data-testid={`mock-highlight-${highlight.id}`}
        onclick={() => openHighlight(highlight.id)}
      >
        {highlight.content?.text || `Highlight ${highlight.id}`}
      </button>
    {/each}
  </div>

  {#if activeHighlightId}
    {@const activeHighlight = highlights.find((highlight) => highlight.id === activeHighlightId)}
    {#if activeHighlight}
      <div data-testid="mock-highlight-popup">
        {#if pinned && editHighlightPopup}
          {@render editHighlightPopup(activeHighlight)}
        {:else if highlightPopup}
          {@render highlightPopup(activeHighlight, setPinned)}
        {/if}
      </div>
    {/if}
  {/if}
</div>
