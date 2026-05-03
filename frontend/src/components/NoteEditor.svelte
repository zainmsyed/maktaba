<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';

  export let placement: 'sidebar' | 'popup' = 'sidebar';
  export let initialContent: string = '';
  export let ariaLabel: string = 'Note content';
  export let highlight: any = null;
  export let onChange: ((draft: string) => void) | null = null;
  export let onSave: ((draft: string) => Promise<any>) | null = null;
  export let onClose: (() => void) | null = null;
  export let autoFocus = false;

  const dispatch = createEventDispatcher();

  let draft: string = initialContent ?? '';
  let savedDraft: string = initialContent ?? '';
  let status: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
  let autosaveTimer: number | null = null;
  let savedClearTimer: number | null = null;
  let textareaEl: HTMLTextAreaElement | null = null;
  let focusRetryTimers: number[] = [];
  let focusRetryFrame: number | null = null;
  let skipDestroyAutosave = false;

  function focusTextarea() {
    textareaEl?.focus({ preventScroll: true });
    textareaEl?.setSelectionRange?.(textareaEl.value.length, textareaEl.value.length);
  }

  function queueFocusRetries() {
    void tick().then(() => {
      focusTextarea();
      if (typeof window === 'undefined') return;
      if (focusRetryFrame !== null) window.cancelAnimationFrame(focusRetryFrame);
      focusRetryFrame = window.requestAnimationFrame(() => {
        focusRetryFrame = null;
        focusTextarea();
      });
      for (const delay of [0, 50, 150]) {
        focusRetryTimers.push(window.setTimeout(focusTextarea, delay));
      }
    });
  }

  // expose focus() for tests / callers
  export function focus() {
    focusTextarea();
    queueFocusRetries();
  }

  function clearTimers() {
    if (autosaveTimer !== null) { window.clearTimeout(autosaveTimer); autosaveTimer = null; }
    if (savedClearTimer !== null) { window.clearTimeout(savedClearTimer); savedClearTimer = null; }
    for (const timer of focusRetryTimers) window.clearTimeout(timer);
    focusRetryTimers = [];
    if (focusRetryFrame !== null) { window.cancelAnimationFrame(focusRetryFrame); focusRetryFrame = null; }
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
    const draftAtSave = draft;
    status = 'saving';
    try {
      const saved = await onSave(draftAtSave);
      if (!saved) { status = 'error'; dispatch('error', { error: 'save-failed' }); return null; }
      const newContent = saved?.content ?? (typeof saved === 'string' ? saved : draftAtSave);
      savedDraft = newContent;
      // Only overwrite draft if the user hasn't typed new content while the save was in flight.
      if (draft === draftAtSave) {
        draft = newContent;
      }
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

  // programmatic save for external callers
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

  async function closePopupEditor() {
    skipDestroyAutosave = true;
    clearTimers();
    if (draft !== savedDraft && onSave) {
      await runSave();
    }
    onClose?.();
    dispatch('close');
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && placement === 'popup') {
      e.stopPropagation();
      e.preventDefault();
      void closePopupEditor();
    }
  }

  onMount(() => {
    resetStatus();
    window.addEventListener('keydown', handleKeydown);
    if (autoFocus || placement === 'popup') {
      queueFocusRetries();
    }
  });

  onDestroy(() => {
    if (!skipDestroyAutosave && draft !== savedDraft && onSave) {
      void runSave();
    }
    clearTimers();
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

<!-- Use the shared paper-editor classes so the note UI matches the rest of the app -->
<div class="paper-editor ne-shell ne-shell--{placement}">
  {#if placement === 'sidebar'}
    <div class="ne-header">
      <div class="ne-header-left">
        <button
          type="button"
          class="paper-btn ne-back-btn"
          on:click={() => { onClose?.(); dispatch('close'); }}
          aria-label="Close note editor"
        >
          ← back
        </button>

        <p class="paper-editor-label ne-label">Document note editor</p>
      </div>

      <span class="paper-save-status ne-status ne-status--{status}" aria-live="polite">
        {#if status === 'saving'}
          <svg class="ne-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <span>Saving…</span>
        {:else if status === 'saved'}
          <span>Saved</span>
        {:else if status === 'error'}
          <span>Unable to save note</span>
        {/if}
      </span>
    </div>
  {:else if status !== 'idle'}
    <div class="ne-header ne-header--popup">
      <span class="paper-save-status ne-status ne-status--{status}" aria-live="polite">
        {#if status === 'saving'}
          <svg class="ne-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          <span>Saving…</span>
        {:else if status === 'saved'}
          <span>Saved</span>
        {:else if status === 'error'}
          <span>Unable to save note</span>
        {/if}
      </span>
    </div>
  {/if}

  {#if placement !== 'popup' && highlight?.extracted_text}
    <p class="paper-editor-quote ne-quote">{highlight.extracted_text}</p>
  {/if}

  <textarea
    bind:this={textareaEl}
    class="paper-editor-textarea ne-textarea"
    placeholder={placement === 'popup' ? 'Add a note for this highlight…' : 'Write a note for this document…'}
    aria-label={ariaLabel}
    data-autofocus={autoFocus || placement === 'popup' ? 'true' : undefined}
    bind:value={draft}
    on:input={handleInput}
  ></textarea>

  {#if status === 'idle' && placement !== 'popup'}
    <p class="paper-save-status ne-hint">
      {highlight ? 'Start typing to autosave this highlight note.' : 'Start typing to autosave this document note.'}
    </p>
  {/if}
</div>

<style>
  /* Minimal overrides - prefer the global paper theme classes */
  .ne-shell { padding: 0; }
  .ne-shell--popup {
    padding: 0;
    background: transparent !important;
    border-top: 0 !important;
    color: var(--ink);
  }
  .ne-shell--popup .ne-label,
  .ne-shell--popup .ne-status,
  .ne-shell--popup .ne-hint,
  .ne-shell--popup .ne-textarea,
  .ne-shell--popup .ne-quote {
    color: inherit;
  }
  .ne-shell--popup .ne-quote { color: var(--ink-2); }
  .ne-shell--popup .ne-textarea::placeholder { color: var(--ink-3); }

  .ne-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .ne-header--popup { justify-content: flex-end; min-height: 18px; margin-bottom: 0; }
  .ne-header-left { display: flex; align-items: center; gap: 10px; min-width: 0; }

  /* Keep a small size for the back button so it doesn't dominate */
  .ne-back-btn { padding: 4px 8px; font-size: 11px; }

  .ne-spin { width: 12px; height: 12px; animation: ne-spin 0.8s linear infinite; }
  @keyframes ne-spin { to { transform: rotate(360deg); } }

  /* Ensure the paper-editor textarea uses the app's UI rhythm */
  .paper-editor-textarea { font-family: var(--font-mono); font-size: 11.5px; }
  .ne-shell--popup .paper-editor-textarea {
    font-family: var(--font-serif);
    font-size: 15px;
    line-height: 1.65;
    min-height: 88px;
    width: 100%;
    resize: none;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .paper-editor-quote { font-size: 11px; }
  .paper-save-status { font-size: 10px; }
</style>
