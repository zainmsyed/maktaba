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
  <meta
    name="description"
    content="Maktaba is a self-hosted reading and note-taking app."
  />
</svelte:head>

<main class="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-12 sm:px-10 lg:px-12">
  <section class="w-full rounded-3xl border border-slate-700/70 bg-slate-900/75 p-8 shadow-2xl shadow-cyan-950/20 backdrop-blur sm:p-10">
    <div class="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
      <div class="max-w-2xl space-y-6">
        <div class="space-y-3">
          <p class="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-300">
            Maktaba scaffold
          </p>
          <h1 class="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Read, highlight, and note — locally.
          </h1>
          <p class="max-w-xl text-base leading-7 text-slate-300 sm:text-lg">
            The frontend shell is running inside Docker and waiting on the FastAPI backend.
            This is the first step toward a self-hosted PDF and EPUB reading workspace.
          </p>
        </div>

        <div class="flex flex-wrap gap-3">
          <a
            class="inline-flex items-center rounded-full border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-300 hover:bg-cyan-300/15"
            href={healthUrl}
            target="_blank"
            rel="noreferrer"
          >
            Open backend health route
          </a>
          <div class="inline-flex items-center rounded-full border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-300">
            API: {data.apiUrl}
          </div>
        </div>
      </div>

      <aside class="min-w-72 rounded-2xl border border-slate-700 bg-slate-950/70 p-6">
        <p class="text-sm font-medium uppercase tracking-[0.25em] text-slate-400">Runtime status</p>
        <div class="mt-4 flex items-center gap-3">
          <span
            class={`inline-flex rounded-full px-3 py-1 text-sm font-semibold uppercase tracking-[0.2em] ${
              backendStatus === 'ok'
                ? 'bg-emerald-500/15 text-emerald-300'
                : backendStatus === 'offline'
                  ? 'bg-rose-500/15 text-rose-300'
                  : 'bg-amber-500/15 text-amber-300'
            }`}
          >
            {backendStatus}
          </span>
        </div>
        <p class="mt-4 text-sm leading-6 text-slate-300">{backendDetail}</p>
        <dl class="mt-6 space-y-4 text-sm text-slate-300">
          <div class="flex items-start justify-between gap-4 border-t border-slate-800 pt-4">
            <dt class="text-slate-500">Frontend</dt>
            <dd class="text-right text-slate-100">SvelteKit</dd>
          </div>
          <div class="flex items-start justify-between gap-4 border-t border-slate-800 pt-4">
            <dt class="text-slate-500">Backend</dt>
            <dd class="text-right text-slate-100">FastAPI</dd>
          </div>
          <div class="flex items-start justify-between gap-4 border-t border-slate-800 pt-4">
            <dt class="text-slate-500">Storage</dt>
            <dd class="text-right text-slate-100">Postgres + /data</dd>
          </div>
        </dl>
      </aside>
    </div>
  </section>
</main>
