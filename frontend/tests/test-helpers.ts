import { vi } from 'vitest';

export async function advanceAndFlush(ms = 0) {
  // Advance fake timers and flush microtasks to stabilize DOM updates.
  await vi.advanceTimersByTimeAsync(ms);
  // flush pending microtasks / Promise resolution queues
  await Promise.resolve();
  await Promise.resolve();
}
