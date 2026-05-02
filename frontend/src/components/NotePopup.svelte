<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';

  export let ariaLabel = 'Note popup';
  export let title: string = 'highlight';
  export let onClose: (() => void) | null = null;

  let popupEl: HTMLDivElement | null = null;
  let keydownHandler: ((event: KeyboardEvent) => void) | null = null;

  function getFocusableElements() {
    if (!popupEl) return [] as HTMLElement[];
    return Array.from(
      popupEl.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => !el.hasAttribute('disabled'));
  }

  function focusFirst() {
    const focusable = getFocusableElements();
    const preferred =
      focusable.find((el) => el.hasAttribute('data-autofocus')) ??
      focusable.find((el) => el instanceof HTMLTextAreaElement) ??
      focusable[0];
    (preferred ?? popupEl)?.focus?.();
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') { onClose?.(); return; }
    if (event.key !== 'Tab' || !popupEl) return;
    const focusable = getFocusableElements();
    if (focusable.length === 0) { event.preventDefault(); popupEl.focus(); return; }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (event.shiftKey && active === first) { event.preventDefault(); last.focus(); return; }
    if (!event.shiftKey && active === last) { event.preventDefault(); first.focus(); }
  }

  onMount(() => {
    void tick().then(focusFirst);
    keydownHandler = handleKeydown;
    window.addEventListener('keydown', keydownHandler, true);
  });

  onDestroy(() => {
    if (keydownHandler) window.removeEventListener('keydown', keydownHandler, true);
  });
</script>

<div
  bind:this={popupEl}
  class="Highlight__popup np-popup"
  role="dialog"
  aria-modal="true"
  aria-label={ariaLabel}
  tabindex="-1"
>
  <!-- Header -->
  <div class="np-header">
    <span class="np-title">{title}</span>
    {#if onClose}
      <button class="np-close" type="button" on:click={onClose} aria-label="Close">✕</button>
    {/if}
  </div>

  <slot />
</div>

<style>
  .np-popup {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 280px;
    max-width: 340px;
    background: var(--paper);
    border: 0.5px solid rgba(26,24,20,0.14);
    border-radius: 10px;
    box-shadow: 0 8px 28px rgba(0,0,0,.10), 0 2px 8px rgba(0,0,0,.07);
    padding: 14px 16px 16px;
    outline: none;
  }

  .np-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .np-title {
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 300;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .np-close {
    font-size: 12px;
    color: var(--ink-3);
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 6px;
    line-height: 1;
    transition: color 0.15s, background 0.15s;
  }
  .np-close:hover { color: var(--ink); background: var(--paper-2); }
</style>
