<script lang="ts">
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { tick } from 'svelte';

  export let placement: 'sidebar' | 'popup' = 'sidebar';
  export let initialContent: string = '';
  export let ariaLabel: string = 'Note content';
  export let highlight: any = null;
  export let onSave: ((draft: string) => Promise<any>) | null = null;
  export let onClose: (() => void) | null = null;

  const dispatch = createEventDispatcher();

  let draft: string = initialContent ?? '';
  let savedDraft: string = initialContent ?? '';
  let status: 'muted' | 'saving' | 'saved' | 'error' = 'muted';
  let statusText = 'Autosaves after 500ms';
  let autosaveTimer: number | null = null;
  let savedClearTimer: number | null = null;
  let textareaEl: HTMLTextAreaElement | null = null;

  // expose focus API for tests and callers
  export function focus() {
    textareaEl?.focus();
    textareaEl?.setSelectionRange?.(textareaEl.value.length, textareaEl.value.length);
  }

  function clearTimers() {
    if (autosaveTimer !== null) {
      window.clearTimeout(autosaveTimer);
      autosaveTimer = null;
    }
    if (savedClearTimer !== null) {
      window.clearTimeout(savedClearTimer);
      savedClearTimer = null;
    }
  }

  function resetStatus() {
    status = 'muted';
    statusText = placement === 'popup' && highlight ? 'Start typing to autosave this highlight note.' : 'Start typing to autosave this document note.';
  }

  function scheduleSavedNoteFade() {
    if (savedClearTimer !== null) {
      window.clearTimeout(savedClearTimer);
    }
    savedClearTimer = window.setTimeout(() => {
      savedClearTimer = null;
      if (draft !== savedDraft) return;
      resetStatus();
    }, 2000);
  }

  async function runSave() {
    if (!onSave) return null;
    status = 'saving';
    statusText = 'Saving…';
    try {
      const saved = await onSave(draft);
      if (!saved) {
        status = 'error';
        statusText = 'Unable to save note';
        dispatch('error', { error: 'save-failed' });
        return null;
      }
      const newContent = saved?.content ?? (typeof saved === 'string' ? saved : draft);
      savedDraft = newContent;
      draft = newContent;
      status = 'saved';
      statusText = 'Saved';
      scheduleSavedNoteFade();
      dispatch('saved', { note: saved });
      return saved;
    } catch (e) {
      status = 'error';
      statusText = 'Unable to save note';
      dispatch('error', { error: e });
      return null;
    }
  }

  // expose a programmatic save for external callers (flush)
  export function save() {
    return runSave();
  }

  function handleInput(e: Event) {
    const target = e.currentTarget as HTMLTextAreaElement;
    draft = target.value;
    if (draft === savedDraft) {
      clearTimers();
      resetStatus();
      return;
    }

    clearTimers();
    status = 'saving';
    statusText = 'Saving…';
    autosaveTimer = window.setTimeout(() => {
      autosaveTimer = null;
      void runSave();
    }, 500);
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

<div class={`space-y-3 rounded-2xl border ${placement === 'popup' ? 'border-slate-700/80 bg-slate-950/95 p-3' : 'border-slate-800 bg-slate-950/70 p-4'}`}>
  <div class="flex items-start justify-between gap-3">
    <div class="min-w-0">
      <p class="text-[10px] uppercase tracking-[0.24em] text-slate-500">
        {placement === 'popup' ? 'Highlight note editor' : 'Document note editor'}
      </p>
      <p class="mt-1 text-sm text-slate-200">
        {#if placement === 'popup' && highlight}
          Page {highlight.page_number}
        {:else}
          Standalone document note
        {/if}
      </p>
    </div>

    <span class={`inline-flex shrink-0 items-center gap-2 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${status === 'saving' ? 'bg-amber-500/15 text-amber-300' : status === 'saved' ? 'bg-emerald-500/15 text-emerald-300' : status === 'error' ? 'bg-rose-500/15 text-rose-300' : 'bg-slate-800 text-slate-400'}`}>
      {#if status === 'saving'}
        <svg class="animate-spin h-3 w-3 text-amber-300" viewBox="0 0 24 24" fill="none"><path d="M12 2v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      {/if}
      <span>{statusText}</span>
    </span>
  </div>

  {#if highlight?.extracted_text}
    <p class="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
      {highlight.extracted_text}
    </p>
  {/if}

  <textarea
    bind:this={textareaEl}
    class={`w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-400/40 focus:ring-1 focus:ring-cyan-400/20 ${placement === 'popup' ? 'min-h-28' : 'min-h-36'}`}
    placeholder={placement === 'popup' ? 'Add a note for this highlight…' : 'Write a standalone note for this document…'}
    aria-label={ariaLabel}
    bind:value={draft}
    on:input={handleInput}
  ></textarea>

  <p class="text-xs text-slate-500">
    {#if status === 'saved'}
      Saved note will fade from the badge after a moment.
    {:else if status === 'saving'}
      Autosaves after 500ms of inactivity.
    {:else if status === 'error'}
      Try typing again to retry saving.
    {:else}
      {statusText}
    {/if}
  </p>
</div>

<style>
  /* keep minimal custom styles; Tailwind handles most tokens */
</style>
