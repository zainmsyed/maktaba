import { describe, expect, it } from 'vitest';
import { computeProgressPercent } from '../src/lib/progress';

describe('computeProgressPercent', () => {
  it('returns 0 when not started (page < 1)', () => {
    expect(computeProgressPercent(0, 10)).toBe(0);
    expect(computeProgressPercent(-1, 10)).toBe(0);
  });

  it('returns 0 for total <= 0', () => {
    expect(computeProgressPercent(1, 0)).toBe(0);
    expect(computeProgressPercent(1, -5)).toBe(0);
  });

  it('returns 100 when at or past the last page', () => {
    expect(computeProgressPercent(10, 10)).toBe(100);
    expect(computeProgressPercent(15, 10)).toBe(100);
  });

  it('returns 100 for a single-page document', () => {
    expect(computeProgressPercent(1, 1)).toBe(100);
    expect(computeProgressPercent(0, 1)).toBe(0);
  });

  it('returns 0 at page 1 of a multi-page document (baseline)', () => {
    expect(computeProgressPercent(1, 5)).toBe(0);
    expect(computeProgressPercent(1, 100)).toBe(0);
  });

  it('scales correctly from page 2 onward', () => {
    expect(computeProgressPercent(2, 3)).toBe(50);  // (1/2)*100
    expect(computeProgressPercent(3, 5)).toBe(50);  // (2/4)*100
    expect(computeProgressPercent(2, 5)).toBe(25);  // (1/4)*100
    expect(computeProgressPercent(4, 5)).toBe(75);  // (3/4)*100
  });

  it('returns 100 on the last page', () => {
    expect(computeProgressPercent(5, 5)).toBe(100);
    expect(computeProgressPercent(100, 100)).toBe(100);
  });
});
