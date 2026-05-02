import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import NoteEditor from '../src/components/NoteEditor.svelte';
import NotePopupHarness from './mocks/NotePopupHarness.svelte';
import NotePopupTextareaHarness from './mocks/NotePopupTextareaHarness.svelte';
import { advanceAndFlush } from './test-helpers';

describe('NoteEditor', () => {
  it('exposes focus and autosaves with saved fade', async () => {
    vi.useFakeTimers();
    const onChange = vi.fn();
    const onSave = vi.fn(async (draft: string) => ({ id: 'note-1', content: draft }));

    const { component, container, getByRole, getByText } = render(NoteEditor, {
      props: {
        placement: 'sidebar',
        initialContent: '',
        ariaLabel: 'Note content',
        onChange,
        onSave,
      },
    });

    const textarea = getByRole('textbox', { name: 'Note content' });
    component.focus();
    expect(document.activeElement).toBe(textarea);
    expect({
      ariaLabel: textarea.getAttribute('aria-label'),
      hint: container.querySelector('.ne-hint')?.textContent?.trim(),
      placeholder: textarea.getAttribute('placeholder'),
    }).toMatchInlineSnapshot(`
      {
        "ariaLabel": "Note content",
        "hint": "Start typing to autosave this document note.",
        "placeholder": "Write a note for this document…",
      }
    `);

    await fireEvent.input(textarea, { target: { value: 'Snapshot note' } });
    expect(onChange).toHaveBeenCalledWith('Snapshot note');
    expect(getByText('Saving…')).toBeTruthy();

    await advanceAndFlush(500);
    await advanceAndFlush(0);

    expect(onSave).toHaveBeenCalledWith('Snapshot note');
    expect(getByText('Saved')).toBeTruthy();

    await advanceAndFlush(2000);
    await advanceAndFlush(0);

    expect(container.textContent).toContain('Start typing to autosave this document note.');
  });
});

describe('NotePopup', () => {
  it('traps focus within the popup content', async () => {
    vi.useFakeTimers();
    render(NotePopupHarness);

    await advanceAndFlush(0);

    const first = document.querySelector('button:first-of-type') as HTMLButtonElement | null;
    const second = document.querySelector('button:last-of-type') as HTMLButtonElement | null;

    expect(first).toBeTruthy();
    expect(second).toBeTruthy();
    expect(document.activeElement).toBe(first);

    second?.focus();
    expect(document.activeElement).toBe(second);

    await fireEvent.keyDown(window, { key: 'Tab' });

    expect(document.activeElement).toBe(first);
  });

  it('prefers the note textarea when the popup opens', async () => {
    vi.useFakeTimers();
    const { getByRole } = render(NotePopupTextareaHarness);

    await advanceAndFlush(0);

    expect(document.activeElement).toBe(getByRole('textbox', { name: 'Note content' }));
  });
});
