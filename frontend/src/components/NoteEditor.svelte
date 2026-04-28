<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';

  export let placement: 'sidebar' | 'popup' = 'sidebar';
  export let initialContent: string = '';
  export let ariaLabel: string = 'Note content';
  export let highlight: any = null;
  export let onChange: ((draft: string) => void) | null = null;
  export let onSave: ((draft: string) => Promise<any>) | null = null;
  export let onClose: (() => void) | null = null;

  const dispatch = createEventDispatcher();

  let draft: string = initialContent ?? '';
  let savedDraft: string = initialContent ?? '';
  let status: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
  let autosaveTimer: number | null = null;
  let savedClearTimer: number | null = null;
  let textareaEl: HTMLTextAreaElement | null = null;

  export function focus() {
    textareaEl?.focus();
    textareaEl?.setSelectionRange?.(textareaEl.value.length, textareaEl.value.length);
  }

  function clearTimers() {
    if (autosaveTimer !== null) { window.clearTimeout(autosaveTimer); autosaveTimer = null; }
    if (savedClearTimer !== null) { window.clearTimeout(savedClearTimer); savedClearTimer = null; }
  }

  function resetStatus() { status = 'idle'; }

  function scheduleSavedNoteFade() {
    if (savedClearTimer !== null) window.clearTimeout(savedClearTimer);
    savedClearTimer = window.setTimeout(() => {
      savedClearTimer = null;
      if (draft !== savedDraft) return;
      resetStatus();
    }, 2000);
  }

  async function runSave() {
    if (!onSave) return null;
    status = 'saving';
    try {
      const saved = await onSave(draft);
      if (!saved) { status = 'error'; dispatch('error', { error: 'save-failed' }); return null; }
      const newContent = saved?.content ?? (typeof saved === 'string' ? saved : draft);
      savedDraft = newContent;
      draft = newContent;
      status = 'saved';
      scheduleSavedNoteFade();
      dispatch('saved', { note: saved });
      return saved;
    } catch (e) {
      status = 'error';
      dispatch('error', { error: e });
      return null;
    }
  }

  export function save() { return runSave(); }

  function handleInput(e: Event) {
    const target = e.currentTarget as HTMLTextAreaElement;
    draft = target.value;
    if (draft === savedDraft) { clearTimers(); resetStatus(); return; }
    clearTimers();
    status = 'saving';
    autosaveTimer = window.setTimeout(() => { autosaveTimer = null; void runSave(); }, 500);
    onChange?.(draft);
    dispatch('change', { value: draft });
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && placement === 'popup') {
      e.stopPropagation();
      onClose?.();
      dispatch('close');
    }
  }

  onMount(() => {
    resetStatus();
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    clearTimers();
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

<div class="ne-shell ne-shell--{placement}">
  <!-- Header row -->
  <div class="ne-header">
    <div class="ne-header-left">
      {#if placement === 'sidebar'}
        <button class="ne-back-btn" type="button" on:click={() => { onClose?.(); dispatch('close'); }} aria-label="Close note editor">
          ← back
        </button>
      {/if}
      <span class="ne-label">
        {placement === 'popup' ? 'highlight note' : 'document note'}
      </span>
    </div>

    <!-- Save status badge -->
    <span class="ne-status ne-status--{status}" aria-live="polite">
      {#if status === 'saving'}
        <svg class="ne-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>Saving…</span>
      {:else if status === 'saved'}
        <span>Saved</span>
      {:else if status === 'error'}
        <span>Unable to save note</span>
      {/if}
    </span>
  </div>

  <!-- Highlight quote (popup only) -->
  {#if highlight?.extracted_text}
    <p class="ne-quote">{highlight.extracted_text}</p>
  {/if}

  <!-- Textarea -->
  <textarea
    bind:this={textareaEl}
    class="ne-textarea"
    placeholder={placement === 'popup' ? 'Add a note for this highlight…' : 'Write a note for this document…'}
    aria-label={ariaLabel}
    bind:value={draft}
    on:input={handleInput}
  ></textarea>

  <!-- Idle hint -->
  {#if status === 'idle'}
    <p class="ne-hint">
      {placement === 'popup' && highlight ? 'Start typing to autosave this highlight note.' : 'Start typing to autosave this document note.'}
    </p>
  {/if}
</div>

<style>
  .ne-shell {
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: var(--paper);
    border-top: 0.5px solid var(--rule);
    padding: 14px 18px 16px;
  }
  .ne-shell--popup {
    background: transparent;
    border-top: none;
    padding: 0;
    gap: 8px;
  }

  .ne-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .ne-header-left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .ne-back-btn {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 300;
    letter-spacing: 0.05em;
    color: var(--ink-3);
    background: transparent;
    border: 0.5px solid var(--rule);
    border-radius: 5px;
    padding: 3px 8px;
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.15s, color 0.15s;
  }
  .ne-back-btn:hover { background: var(--paper-2); color: var(--ink); }

  .ne-label {
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 300;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  /* Status badge */
  .ne-status {
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 300;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    flex-shrink: 0;
    min-width: 0;
    color: transparent; /* invisible when idle */
    background: transparent;
    transition: color 0.2s, background 0.2s;
  }
  .ne-status--saving {
    color: #92400e;
    background: rgba(245,158,11,.12);
  }
  .ne-status--saved {
    color: #166534;
    background: rgba(34,197,94,.12);
  }
  .ne-status--error {
    color: #be123c;
    background: rgba(244,63,94,.12);
  }

  .ne-spin {
    width: 10px;
    height: 10px;
    animation: ne-spin 0.8s linear infinite;
    flex-shrink: 0;
  }
  @keyframes ne-spin { to { transform: rotate(360deg); } }

  /* Quote block */
  .ne-quote {
    font-family: var(--font-serif);
    font-size: 13px;
    font-style: italic;
    color: var(--ink-2);
    border-left: 1.5px solid var(--accent-soft);
    padding-left: 9px;
    margin: 0;
    line-height: 1.6;
  }

  /* Textarea */
  .ne-textarea {
    width: 100%;
    min-height: 110px;
    font-family: var(--font-serif);
    font-size: 13px;
    font-weight: 400;
    line-height: 1.6;
    color: var(--ink);
    background: var(--paper-2);
    border: 0.5px solid var(--rule);
    border-radius: 6px;
    padding: 12px 14px;
    outline: none;
    resize: none;
    transition: border-color 0.15s, background 0.15s;
  }
  .ne-textarea:focus {
    background: var(--paper);
    border-color: rgba(184,92,46,0.30);
  }
  .ne-textarea::placeholder { color: var(--ink-3); }
  .ne-hint {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 300;
    color: var(--ink-3);
    letter-spacing: 0.04em;
    margin: 0;
  }
</style>
