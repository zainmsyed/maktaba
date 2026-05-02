/**
 * Compute reading progress as a percent (0–100).
 *
 * - currentPage < 1  → 0%
 * - currentPage >= totalPages → 100%
 * - totalPages === 1 and currentPage >= 1 → 100%
 * - Otherwise scales from page 2 onward: (currentPage - 1) / (totalPages - 1)
 */
export function computeProgressPercent(currentPage: number, totalPages: number): number {
  const total = Math.max(0, totalPages);
  const page = Math.max(0, currentPage);
  if (total <= 0) return 0;
  if (page < 1) return 0;
  if (page >= total) return 100;
  if (total === 1) return 100;
  return Math.round(((page - 1) / (total - 1)) * 100);
}
