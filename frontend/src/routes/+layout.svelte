<script lang="ts">
  import { onMount } from 'svelte';
  import '../app.css';

  let theme: 'light' | 'dark' = 'light';

  function applyTheme(nextTheme: 'light' | 'dark') {
    theme = nextTheme;
    document.documentElement.setAttribute('data-theme', nextTheme);
    try {
      localStorage.setItem('maktaba:theme', nextTheme);
    } catch {}
  }

  function toggleTheme() {
    applyTheme(theme === 'dark' ? 'light' : 'dark');
  }

  onMount(() => {
    const current = document.documentElement.getAttribute('data-theme');
    theme = current === 'dark' ? 'dark' : 'light';
  });
</script>

<slot />

<button
  type="button"
  class="theme-toggle paper-btn"
  aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  on:click={toggleTheme}
>
  {#if theme === 'dark'}
    <span aria-hidden="true">☼</span>
    <span>Light</span>
  {:else}
    <span aria-hidden="true">☾</span>
    <span>Dark</span>
  {/if}
</button>

<style>
  .theme-toggle {
    position: fixed;
    right: 18px;
    bottom: 18px;
    z-index: 1000;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--panel-bg-strong);
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(8px);
  }
</style>
