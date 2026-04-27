<script lang="ts">
  import { onMount } from 'svelte';

  let {
    highlightsStore,
    style = '',
    onHighlightsRendered,
    pdfHighlighterUtils = $bindable({}),
  }: any = $props();

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
    onHighlightsRendered?.();
  });

  function createTextHighlight() {
    highlightsStore.addHighlight({
      type: 'text',
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
</script>

<div data-testid="pdf-viewer" class="PdfHighlighter" style={style}>
  <div class="page" data-page-number="1">
    <div role="presentation" data-testid="pdf-text-layer-host" onmouseup={createTextHighlight}>Mock text layer</div>
  </div>
  <div class="page" data-page-number="2"></div>
  <div class="page" data-page-number="3"></div>
</div>
