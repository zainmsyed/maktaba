<script lang="ts">
  let { pdfHighlighterWrapper }: any = $props();
</script>

<div data-testid="mock-pdf-loader">
  {@render pdfHighlighterWrapper({ numPages: 3 })}
</div>
