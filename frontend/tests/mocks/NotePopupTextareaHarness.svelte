<script lang="ts">
  import NotePopup from '../../src/components/NotePopup.svelte';
</script>

<NotePopup ariaLabel="Popup textarea test">
  <button type="button">First</button>
  <textarea aria-label="Note content" data-autofocus></textarea>
  <button type="button">Second</button>
</NotePopup>
