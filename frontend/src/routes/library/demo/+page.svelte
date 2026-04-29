<script lang="ts">
  import { onMount } from 'svelte';

  onMount(() => {
    const notesData: any = {
      n1: {
        loc: 'p. 47 · ch. 3',
        quote: '"System 1 operates automatically and quickly, with little or no effort..."',
        body: "Core tension of the book. System 1 is what creates heuristic errors — fast and confident. Connects to Taleb's narrative fallacy: we construct explanations automatically without noticing.",
        color: 'y'
      },
      n2: {
        loc: 'p. 47 · ch. 3',
        quote: '"When we think of ourselves, we identify with System 2..."',
        body: "The illusion of rational agency. We think we are the deliberate thinker but most decisions are already made. Compare to Haidt's rider and elephant.",
        color: 'g'
      },
      n3: {
        loc: 'p. 48 · ch. 3',
        quote: '"There is no part of the brain that either of these systems would call home."',
        body: "Important caveat — System 1/2 is a useful fiction, not neuroscience. The model describes behaviour not anatomy. Be careful citing this as literal brain science.",
        color: 'b'
      },
      n4: {
        loc: 'p. 31 · ch. 2',
        quote: '"The bat and ball problem..."',
        body: "Classic System 1 override. I got this wrong on first read too. The correct answer feels wrong even after you know it.",
        color: 'y'
      },
      n5: {
        loc: 'p. 22 · ch. 1',
        quote: '"A general law of least effort..."',
        body: "Cognitive ease as a default. Question this: is laziness really a law or just a tendency? Feels like it elides counterexamples from sports, craft, creativity.",
        color: 'r'
      }
    };

    let activeNoteId = 'n1';
    let saveTimer: any = null;
    let activeColorFilter: string | null = null;
    let activeSearchQuery = '';

    function activateNote(hlId: string | null, noteId: string | null) {
      document.querySelectorAll('.hl').forEach(el => el.classList.remove('active'));
      if (hlId) {
        const hl = document.getElementById(hlId as string);
        if (hl) hl.classList.add('active');
      }
      if (noteId) selectNote(noteId);
    }

    function selectNote(noteId: string) {
      document.querySelectorAll('.note-item').forEach(el => el.classList.remove('active'));
      const item = document.getElementById(noteId as string);
      if (item) {
        item.classList.add('active');
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
      const n = notesData[noteId];
      if (!n) return;
      activeNoteId = noteId;
      const editorLabel = document.getElementById('editor-label');
      if (editorLabel) editorLabel.textContent = 'note — ' + n.loc.split(' · ')[0];
      const editorQuote = document.getElementById('editor-quote');
      if (editorQuote) editorQuote.textContent = n.quote;
      const textarea = document.getElementById('note-textarea') as HTMLTextAreaElement | null;
      if (textarea) textarea.value = n.body;
      const saveStatus = document.getElementById('save-status');
      if (saveStatus) saveStatus.textContent = 'saved';
    }

    function applyFilters() {
      // Only filter items inside the sidebar; do not hide inline reader text
      document.querySelectorAll('#notes-list .note-item').forEach((item) => {
        const el = item as HTMLElement;
        const text = el.textContent ? el.textContent.toLowerCase() : '';
        const matchesSearch = activeSearchQuery ? text.includes(activeSearchQuery) : true;
        const matchesColor = activeColorFilter ? el.getAttribute('data-color') === activeColorFilter : true;
        el.style.display = matchesSearch && matchesColor ? '' : 'none';
      });

      // Only affect the highlights list in the sidebar (panel-highlights), not inline highlights in the reader
      document.querySelectorAll('#panel-highlights .hl').forEach((item) => {
        const el = item as HTMLElement;
        const matchesColor = activeColorFilter ? el.getAttribute('data-color') === activeColorFilter : true;
        el.style.display = matchesColor ? '' : 'none';
      });

      document.querySelectorAll('.cp').forEach((d) => {
        const color = d.getAttribute('data-color');
        d.classList.toggle('selected', Boolean(activeColorFilter && color === activeColorFilter));
      });
    }

    function setColorFilter(color: string) {
      activeColorFilter = activeColorFilter === color ? null : color;
      applyFilters();
    }

    // Attach event after mount to the dynamic textarea
    function attachTextarea() {
      const ta = document.getElementById('note-textarea');
      if (!ta) return;
      ta.addEventListener('input', function (this: HTMLTextAreaElement) {
        const saveStatus = document.getElementById('save-status');
        if (saveStatus) saveStatus.textContent = 'editing...';
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
          if (!activeNoteId) return;
          notesData[activeNoteId].body = (this as HTMLTextAreaElement).value;
          const item = document.getElementById(activeNoteId as string);
          if (item) {
            const bodyEl = item.querySelector('.note-body');
            if (bodyEl) bodyEl.textContent = (this as HTMLTextAreaElement).value;
          }
          if (saveStatus) saveStatus.textContent = 'saved';
        }, 600);
      });
    }

    function filterNotes(query: string) {
      activeSearchQuery = query.toLowerCase();
      applyFilters();
    }

    function switchTab(tab: string) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      const tabEl = document.getElementById('tab-' + tab);
      if (tabEl) tabEl.classList.add('active');
      const panelNotes = document.getElementById('panel-notes');
      const panelHighlights = document.getElementById('panel-highlights');
      const panelAsk = document.getElementById('panel-ask');
      if (panelNotes) panelNotes.style.display = tab === 'notes' ? 'flex' : 'none';
      if (panelHighlights) panelHighlights.style.display = tab === 'highlights' ? 'block' : 'none';
      if (panelAsk) panelAsk.style.display = tab === 'ask' ? 'flex' : 'none';
    }

    // wire up static event handlers now
    document.querySelectorAll('.note-item').forEach(it => {
      it.addEventListener('click', () => {
        if (it.id) selectNote(it.id);
      });
    });

    document.querySelectorAll('.hl').forEach(el => el.addEventListener('click', (e) => {
      const id = (e.currentTarget as HTMLElement).id;
      const noteId = (e.currentTarget as HTMLElement).getAttribute('data-note-id');
      activateNote(id, noteId || null);
    }));

    document.querySelectorAll('.tab').forEach((el) => el.addEventListener('click', () => {
      const tab = (el as HTMLElement).dataset.tab;
      if (tab) switchTab(tab);
    }));

    document.querySelectorAll('.cp').forEach((el) => el.addEventListener('click', function () {
      setColorFilter((this as HTMLElement).getAttribute('data-color') || 'y');
    }));

    const searchInput = document.getElementById('note-search') as HTMLInputElement | null;
    if (searchInput) searchInput.addEventListener('input', (ev) => filterNotes((ev.target as HTMLInputElement).value));

    attachTextarea();
    applyFilters();
  });
</script>

<svelte:head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
  <style>
/* copy of the reference CSS (trimmed for demo) */
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --ink: #1a1814;
  --ink-2: #4a4640;
  --ink-3: #8a8680;
  --paper: #faf8f4;
  --paper-2: #f2f0eb;
  --paper-3: #e8e5de;
  --accent: #b85c2e;
  --accent-soft: #f0e6dc;
  --rule: rgba(26,24,20,0.1);
  --hl-y: rgba(245,210,100,0.38);
  --hl-g: rgba(100,185,130,0.32);
  --hl-b: rgba(100,150,220,0.3);
}
html, body { width: 100%; height: 100%; font-family: 'Lora', Georgia, serif; background: var(--paper-2); color: var(--ink); overflow: hidden; }
body { margin: 0; }
.shell { display: grid; grid-template-rows: 46px minmax(0, 1fr); grid-template-columns: minmax(0, 1fr) 320px; width: 100vw; height: 100vh; border-radius: 0; overflow: hidden; background: var(--paper); box-shadow: none; }
.topbar { grid-column: 1 / -1; display: flex; align-items: center; padding: 0 22px; border-bottom: 0.5px solid var(--rule); gap: 16px; background: var(--paper); }
.wordmark { font-family: 'Lora', serif; font-size: 15px; font-weight: 500; letter-spacing: 0.07em; color: var(--ink); margin-right: 4px; }
.nav-links { display: flex; gap: 2px; flex: 1; }
.nav-link { font-family: var(--font-serif); font-size: 11px; font-weight: 300; color: var(--ink-3); letter-spacing: 0.06em; padding: 5px 10px; cursor: pointer; border-radius: 5px; transition: color 0.15s, background 0.15s; user-select: none; }
.nav-link:hover { color: var(--ink); background: var(--paper-2); }
.nav-link.active { color: var(--ink); }
.reader { padding: 52px 80px; overflow-y: auto; background: var(--paper); border-right: 0.5px solid var(--rule); position: relative; scroll-behavior: smooth; }
.book-meta { margin-bottom: 32px; }
.book-chapter { font-family: var(--font-serif); font-size: 10px; font-weight: 300; color: var(--ink-3); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px; }
.book-title { font-size: 19px; font-weight: 500; color: var(--ink); line-height: 1.3; }
.rule-line { height: 0.5px; background: var(--rule); margin: 24px 0; }
.prose { font-size: 15.5px; line-height: 1.88; color: var(--ink); }
.prose p { margin-bottom: 1.5em; }
.hl { border-radius: 2px; padding: 1px 0; cursor: pointer; transition: filter 0.12s; }
.hl-y { background: var(--hl-y); }
.note-dot { display: inline-block; width: 5px; height: 5px; border-radius: 50%; background: var(--accent); vertical-align: super; font-size: 0; margin-left: 2px; cursor: pointer; position: relative; top: -1px; }
.sidebar { display: flex; flex-direction: column; background: var(--paper-2); overflow: hidden; }
.sidebar-tabs { display: flex; border-bottom: 0.5px solid var(--rule); padding: 0 18px; flex-shrink: 0; background: var(--paper-2); }
.tab { font-family: var(--font-serif); font-size: 10px; font-weight: 300; letter-spacing: 0.09em; color: var(--ink-3); padding: 14px 10px 12px; cursor: pointer; border-bottom: 1.5px solid transparent; transition: all 0.15s; user-select: none; }
.tab.active { color: var(--ink); border-bottom-color: var(--accent); }
.search-bar-wrap { padding: 10px 16px; border-bottom: 0.5px solid var(--rule); flex-shrink: 0; }
.search-input { width: 100%; font-family: var(--font-serif); font-size: 11px; font-weight: 300; color: var(--ink); background: var(--paper); border: 0.5px solid var(--rule); border-radius: 6px; padding: 7px 10px; outline: none; letter-spacing: 0.02em; transition: border-color 0.15s; }
.notes-list { flex: 1; overflow-y: auto; padding: 0; }
.note-item { padding: 15px 18px; border-bottom: 0.5px solid var(--rule); cursor: pointer; transition: background 0.12s; position: relative; }
.note-item:hover { background: var(--paper); }
.note-item.active { background: var(--paper); }
.note-item.active::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: var(--accent); }
.note-loc { font-family: var(--font-serif); font-size: 9px; font-weight: 300; color: var(--ink-3); letter-spacing: 0.08em; margin-bottom: 7px; display: flex; align-items: center; gap: 4px; }
.note-quote { font-size: 11.5px; line-height: 1.55; color: var(--ink-2); font-style: italic; margin-bottom: 8px; border-left: 1.5px solid var(--paper-3); padding-left: 9px; }
.note-body { font-family: var(--font-serif); font-size: 11px; font-weight: 300; line-height: 1.65; color: var(--ink); }
.note-editor { border-top: 0.5px solid var(--rule); padding: 14px 18px 16px; background: var(--paper); flex-shrink: 0; }
.editor-label { font-family: var(--font-serif); font-size: 9px; font-weight: 300; color: var(--ink-3); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 9px; }
.editor-quote { font-size: 11px; font-style: italic; color: var(--ink-2); border-left: 1.5px solid var(--accent-soft); padding-left: 9px; margin-bottom: 10px; line-height: 1.55; }
.note-textarea { width: 100%; font-family: var(--font-serif); font-size: 11.5px; font-weight: 300; line-height: 1.7; color: var(--ink); background: transparent; border: none; outline: none; resize: none; height: 82px; }
.editor-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.save-status { font-family: var(--font-serif); font-size: 9px; font-weight: 300; color: var(--ink-3); letter-spacing: 0.06em; transition: opacity 0.3s; }
.color-picks { display: flex; gap: 7px; align-items: center; }
.cp { width: 10px; height: 10px; border-radius: 50%; cursor: pointer; border: 1.5px solid transparent; transition: transform 0.1s, border-color 0.1s; }
.cp:hover { transform: scale(1.25); }
.cp.selected { border-color: var(--ink-2); }
.cp-y { background: #c9980a; }
.cp-g { background: #3a9e5f; }
.cp-b { background: #3a72c4; }
.cp-r { background: #c44040; }
/* scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--paper-3); border-radius: 4px; }
  </style>
</svelte:head>

<div class="shell" id="shell">
  <div class="topbar">
    <span class="wordmark">maktaba</span>
    <div class="nav-links">
      <span class="nav-link" id="nav-library">library</span>
      <span class="nav-link active" id="nav-reading">reading</span>
    </div>
    <div class="topbar-right" id="reader-controls">
      <div class="progress-wrap">
        <span class="progress-label">p. 47 of 138</span>
        <div class="progress-bar"><div class="progress-fill"></div></div>
        <span class="progress-label">34%</span>
      </div>
      <div class="icon-btn" title="search notes">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" stroke-width="1.2"/><line x1="10" y1="10" x2="14" y2="14" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
      </div>
      <div class="icon-btn" title="settings">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2.5" stroke="currentColor" stroke-width="1.2"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
      </div>
    </div>
  </div>

  <div class="reader" id="reader-panel">
    <div class="book-meta">
      <div class="book-chapter">Chapter 3 — The Two Systems</div>
      <div class="book-title">Thinking, Fast and Slow</div>
    </div>
    <div class="rule-line"></div>
    <div class="prose">
      <p>Psychologists have been intensely interested in the two modes of thinking represented by the bat-and-ball problem and the Linda problem, and have offered many insights into their characteristics. I adopt terms originally proposed by the psychologists Keith Stanovich and Richard West, and will refer to two systems in the mind, System 1 and System 2.</p>

      <p><span class="hl hl-y" id="hl1" data-color="y" data-note-id="n1"><span class="note-dot"></span>System 1 operates automatically and quickly, with little or no effort and no sense of voluntary control.</span> System 2 allocates attention to the effortful mental activities that demand it, including complex computations. The operations of System 2 are often associated with the subjective experience of agency, choice, and concentration.</p>

      <p>The labels of System 1 and System 2 are now widely used in psychology, but I go further than most in this book, which you can read as a psychologist's view of a conversation between the two fictitious agents in the mind. <span class="hl hl-g" id="hl2" data-color="g" data-note-id="n2">When we think of ourselves, we identify with System 2, the conscious, reasoning self that has beliefs, makes choices, and decides what to think about and what to do.<span class="note-dot"></span></span></p>

      <p>System 1 and System 2 are so central to the story I tell in this book that I must make it absolutely clear that they are fictitious characters. Systems 1 and 2 are not systems in the standard sense of entities with interacting aspects or parts. <span class="hl hl-b" id="hl3" data-color="b" data-note-id="n3">There is no part of the brain that either of these systems would call home.<span class="note-dot"></span></span> The fictitious systems make it easier to think about judgment and choice than the correct but cumbersome statement about fast versus slow mental processes.</p>

      <p>The great comedian Danny Kaye had a line that captures the relationship between System 1 and System 2: "She has beautiful eyes — both of them." The idea of beautiful eyes normally evokes a mental image of a face, not individual eyes. Most of our thinking happens before we are aware it has happened at all.</p>
    </div>
  </div>

  <div class="sidebar" id="sidebar-panel">
    <div class="sidebar-tabs">
      <span class="tab active" id="tab-notes" data-tab="notes" role="button">notes</span>
      <span class="tab" id="tab-highlights" data-tab="highlights" role="button">highlights</span>
      <span class="tab" id="tab-ask" data-tab="ask" role="button">ask</span>
    </div>

    <div id="panel-notes" style="display:flex;flex-direction:column;flex:1;overflow:hidden;">
      <div class="search-bar-wrap">
        <input class="search-input" placeholder="search notes..." type="text" id="note-search" />
      </div>

      <div class="notes-list" id="notes-list">

        <div class="note-item active" id="n1" data-color="y">
          <div class="note-loc"><span class="color-dot dot-y"></span>p. 47 · ch. 3</div>
          <div class="note-quote">"System 1 operates automatically and quickly, with little or no effort..."</div>
          <div class="note-body">Core tension of the book. System 1 is what creates heuristic errors — fast and confident. Connects to Taleb's narrative fallacy: we construct explanations automatically without noticing.</div>
        </div>

        <div class="note-item" id="n2" data-color="g">
          <div class="note-loc"><span class="color-dot dot-g"></span>p. 47 · ch. 3</div>
          <div class="note-quote">"When we think of ourselves, we identify with System 2..."</div>
          <div class="note-body">The illusion of rational agency. We think we are the deliberate thinker but most decisions are already made. Compare to Haidt's rider and elephant.</div>
        </div>

        <div class="note-item" id="n3" data-color="b">
          <div class="note-loc"><span class="color-dot dot-b"></span>p. 48 · ch. 3</div>
          <div class="note-quote">"There is no part of the brain that either of these systems would call home."</div>
          <div class="note-body">Important caveat — System 1/2 is a useful fiction, not neuroscience. The model describes behaviour not anatomy. Be careful citing this as literal brain science.</div>
        </div>

      </div>

      <div class="note-editor" id="editor">
        <div class="editor-label" id="editor-label">note — p. 47</div>
        <div class="editor-quote" id="editor-quote">"System 1 operates automatically and quickly, with little or no effort..."</div>
        <textarea class="note-textarea" id="note-textarea" placeholder="write a note..."></textarea>
        <div class="editor-footer">
          <span class="save-status" id="save-status">saved</span>
          <div class="color-picks">
            <div class="cp cp-y" data-color="y" title="Filter yellow-highlight notes"></div>
            <div class="cp cp-g" data-color="g" title="Filter green-highlight notes"></div>
            <div class="cp cp-b" data-color="b" title="Filter blue-highlight notes"></div>
            <div class="cp cp-r" data-color="r" title="Filter red-highlight notes"></div>
          </div>
        </div>
      </div>
    </div>

    <div id="panel-ask" class="ask-panel" style="display:none;">
      <div class="ask-history">
        <div class="ask-bubble ai">Ask anything about your notes for this book, or across your whole library.<cite>using notes from Thinking, Fast and Slow · 5 notes</cite></div>
      </div>
      <div class="ask-input-row">
        <textarea class="ask-textarea" placeholder="ask your notes..."></textarea>
        <button class="ask-send" aria-label="Send ask prompt" title="Send ask prompt"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 10L10 6L2 2V5.5L7 6L2 6.5V10Z" fill="white"/></svg></button>
      </div>
    </div>

    <div id="panel-highlights" style="display:none;flex:1;overflow-y:auto;">
      <div style="padding:20px 18px;">
        <div style="font-family:var(--font-serif);font-size:10px;font-weight:300;color:var(--ink-3);letter-spacing:0.08em;margin-bottom:16px;">3 highlights · this chapter</div>
        <div style="display:flex;flex-direction:column;gap:12px;">
          <div class="hl hl-y" id="hl1a" style="background:var(--hl-y);border-radius:4px;padding:10px 12px;font-size:12px;line-height:1.6;color:var(--ink);cursor:pointer;" data-color="y" data-hl-id="hl1" data-note-id="n1">"System 1 operates automatically and quickly, with little or no effort and no sense of voluntary control."</div>
          <div class="hl hl-g" id="hl2a" style="background:var(--hl-g);border-radius:4px;padding:10px 12px;font-size:12px;line-height:1.6;color:var(--ink);cursor:pointer;" data-color="g" data-hl-id="hl2" data-note-id="n2">"When we think of ourselves, we identify with System 2, the conscious, reasoning self..."</div>
          <div class="hl hl-b" id="hl3a" style="background:var(--hl-b);border-radius:4px;padding:10px 12px;font-size:12px;line-height:1.6;color:var(--ink);cursor:pointer;" data-color="b" data-hl-id="hl3" data-note-id="n3">"There is no part of the brain that either of these systems would call home."</div>
        </div>
      </div>
    </div>

  </div>
</div>
