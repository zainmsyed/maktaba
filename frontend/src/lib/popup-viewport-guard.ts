/**
 * Shared popup viewport-guard logic.
 *
 * Keeps a `.hl_tip_container` ancestor within the viewport by adjusting its
 * `top` style. Used by both the generic NotePopup component and the reader's
 * highlight popups.
 */

const DEFAULT_SAFE_MARGIN = 12;
const REPOSITION_DELAYS = [0, 30, 120];

function readBaseTop(container: HTMLElement): number | null {
	const currentTop = Number.parseFloat(container.style.top || '');
	const adjustedTop = Number.parseFloat(container.dataset.adjustedTop || '');
	const savedBaseTop = Number.parseFloat(container.dataset.baseTop || '');

	if (!Number.isFinite(currentTop) && !Number.isFinite(savedBaseTop)) {
		return null;
	}

	let baseTop = savedBaseTop;
	if (
		Number.isFinite(currentTop) &&
		(!Number.isFinite(adjustedTop) || Math.abs(currentTop - adjustedTop) > 0.5)
	) {
		baseTop = currentTop;
		container.dataset.baseTop = `${baseTop}`;
	}

	return Number.isFinite(baseTop) ? baseTop : null;
}

function clampTop(
	baseTop: number,
	rect: DOMRect,
	viewportHeight: number,
	safeMargin: number,
): number {
	let nextTop = baseTop;
	if (rect.bottom > viewportHeight - safeMargin) {
		nextTop -= rect.bottom - (viewportHeight - safeMargin);
	}
	if (rect.top < safeMargin) {
		nextTop += safeMargin - rect.top;
	}
	return nextTop;
}

function applyTop(container: HTMLElement, top: number): void {
	container.style.top = `${top}px`;
	container.dataset.adjustedTop = `${top}`;
}

function guardPopupContainer(container: HTMLElement, safeMargin = DEFAULT_SAFE_MARGIN): void {
	const baseTop = readBaseTop(container);
	if (baseTop === null) return;

	applyTop(container, baseTop);
	const rect = container.getBoundingClientRect();
	const nextTop = clampTop(baseTop, rect, window.innerHeight, safeMargin);
	applyTop(container, nextTop);
}

function guardPopupInView(node: HTMLElement, safeMargin = DEFAULT_SAFE_MARGIN): void {
	const container = node.closest<HTMLElement>('.hl_tip_container');
	if (!container) return;
	guardPopupContainer(container, safeMargin);
}

interface PopupViewportGuardOptions {
	safeMargin?: number;
}

/**
 * Imperative helper for components that manage their own lifecycle
 * (e.g. NotePopup via onMount / onDestroy).
 * Returns a cleanup function.
 */
export function keepPopupInView(
	node: HTMLElement,
	options: PopupViewportGuardOptions = {},
): (() => void) | undefined {
	if (typeof window === 'undefined') return undefined;

	const { safeMargin = DEFAULT_SAFE_MARGIN } = options;

	const schedule = () => window.requestAnimationFrame(() => guardPopupInView(node, safeMargin));
	const timers = REPOSITION_DELAYS.map((delay) => window.setTimeout(schedule, delay));

	let resizeObserver: ResizeObserver | null = null;
	if (typeof ResizeObserver !== 'undefined') {
		resizeObserver = new ResizeObserver(schedule);
		resizeObserver.observe(node);
	}
	window.addEventListener('resize', schedule);
	window.addEventListener('scroll', schedule, true);

	return () => {
		resizeObserver?.disconnect();
		for (const timer of timers) window.clearTimeout(timer);
		window.removeEventListener('resize', schedule);
		window.removeEventListener('scroll', schedule, true);
	};
}

/**
 * Svelte action for use with `use:popupViewportGuard`.
 */
export function popupViewportGuard(
	node: HTMLElement,
	options: PopupViewportGuardOptions = {},
) {
	const cleanup = keepPopupInView(node, options);
	return {
		destroy() {
			cleanup?.();
		},
	};
}
