<script lang="ts">
  import { onMount } from 'svelte';

  export let data: App.PageData;

  let backendStatus = 'Checking backend';
  let backendDetail = 'Waiting for the FastAPI health route.';

  const healthUrl = `${data.apiUrl.replace(/\/$/, '')}/health`;

  onMount(async () => {
    try {
      const response = await fetch(healthUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload: { status?: string; service?: string } = await response.json();
      backendStatus = payload.status ?? 'ok';
      backendDetail = `Connected to ${payload.service ?? 'backend'} at ${healthUrl}`;
    } catch (error) {
      backendStatus = 'offline';
      backendDetail = error instanceof Error ? error.message : 'Unknown backend error';
    }
  });
</script>

<svelte:head>
  <title>Maktaba</title>
  <meta name="description" content="Maktaba is a self-hosted reading and note-taking app." />
</svelte:head>

<main class="landing-page">
  <section class="landing-shell">
    <div class="landing-copy">
      <p class="landing-eyebrow">Maktaba</p>
      <h1 class="landing-title">Read, highlight, and note — locally.</h1>
      <p class="landing-body">
        A self-hosted reading workspace for PDFs and EPUBs with highlights, notes, and search.
      </p>

      <div class="landing-actions">
        <a class="paper-btn-accent" href="/library">Open library</a>
        <a class="paper-btn" href={healthUrl} target="_blank" rel="noreferrer">Backend health</a>
      </div>
    </div>

    <aside class="status-card">
      <p class="status-label">Runtime status</p>
      <div class="status-row">
        <span class:status-pill={true} class:status-pill--ok={backendStatus === 'ok'} class:status-pill--offline={backendStatus === 'offline'}>
          {backendStatus}
        </span>
      </div>
      <p class="status-detail">{backendDetail}</p>
      <dl class="status-list">
        <div>
          <dt>Frontend</dt>
          <dd>SvelteKit</dd>
        </div>
        <div>
          <dt>Backend</dt>
          <dd>FastAPI</dd>
        </div>
        <div>
          <dt>Storage</dt>
          <dd>Postgres + /data</dd>
        </div>
      </dl>
    </aside>
  </section>
</main>

<style>
  .landing-page {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 32px;
    color: var(--ink);
  }

  .landing-shell {
    width: min(1100px, 100%);
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 380px);
    gap: 28px;
    align-items: start;
  }

  .landing-copy,
  .status-card {
    border: 1px solid var(--rule);
    background: var(--panel-bg-strong);
    box-shadow: var(--shadow-soft);
    border-radius: 22px;
  }

  .landing-copy {
    padding: 40px;
  }

  .landing-eyebrow,
  .status-label {
    margin: 0 0 10px;
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .landing-title {
    margin: 0 0 16px;
    font-size: clamp(2.2rem, 5vw, 4rem);
    line-height: 1.05;
    color: var(--ink);
  }

  .landing-body,
  .status-detail,
  .status-list {
    color: var(--ink-2);
    line-height: 1.7;
  }

  .landing-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 24px;
  }

  .status-card {
    padding: 24px;
  }

  .status-row {
    margin-bottom: 14px;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 6px 12px;
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    background: var(--paper-2);
    color: var(--ink-2);
  }

  .status-pill--ok {
    background: rgba(100, 185, 130, 0.16);
    color: #3a9e5f;
  }

  .status-pill--offline {
    background: rgba(196, 64, 64, 0.14);
    color: #c44040;
  }

  .status-list {
    margin-top: 18px;
  }

  .status-list div {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding-top: 12px;
    margin-top: 12px;
    border-top: 1px solid var(--rule);
  }

  .status-list dt {
    color: var(--ink-3);
  }

  @media (max-width: 860px) {
    .landing-shell {
      grid-template-columns: 1fr;
    }

    .landing-copy {
      padding: 28px;
    }
  }
</style>
