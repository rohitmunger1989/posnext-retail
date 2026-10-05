/**
 * Responsive Payment Dialog Composable
 * Handles viewport tracking and dynamic sizing for payment dialog
 */

import { ref, computed, onMounted, onUnmounted } from "vue";

export function useResponsivePayment() {
	// Viewport dimension tracking
	const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1200);
	const viewportHeight = ref(typeof window !== "undefined" ? window.innerHeight : 800);

	function updateViewportDimensions() {
		viewportWidth.value = window.innerWidth;
		viewportHeight.value = window.innerHeight;
	}

	onMounted(() => {
		updateViewportDimensions();
		window.addEventListener("resize", updateViewportDimensions);
	});

	onUnmounted(() => {
		window.removeEventListener("resize", updateViewportDimensions);
	});

	// Keep frappe-ui on a desktop-sized shell; the actual rendered dialog width
	// is controlled by the scoped viewport CSS in PaymentDialog.vue.
	const dynamicDialogSize = computed(() => {
		const width = viewportWidth.value;
		if (width < 768) return "full";
		return "5xl";
	});

	// Check if we're on a mobile device (for mobile-specific behavior)
	const isMobileView = computed(() => viewportWidth.value < 1024);

	// Fit desktop content to the current viewport height. Cap the height on large
	// monitors so the payment UI stays comfortable instead of oversized.
	const dialogContentMaxHeight = computed(() => {
		const height = viewportHeight.value;
		const width = viewportWidth.value;

		if (width < 1024) {
			return "none";
		}

		return `${Math.min(720, Math.max(420, height - 118))}px`;
	});

	// Keep the summary column aligned with the available dialog body height.
	const dynamicLeftColumnHeight = computed(() => {
		const height = viewportHeight.value;

		if (viewportWidth.value < 1024) {
			return "auto";
		}

		return `${Math.min(650, Math.max(340, height - 178))}px`;
	});

	// Check if we're in compact mode (small screens)
	const isCompactMode = computed(() => viewportHeight.value < 800 || viewportWidth.value < 1024);

	// Check if we're on a very small mobile screen
	const isSmallMobile = computed(() => viewportWidth.value < 360 || viewportHeight.value < 600);

	// Dynamic gap and padding based on screen size
	const dynamicGap = computed(() => {
		if (viewportWidth.value < 360) return "gap-1"; // Very small phones
		if (viewportWidth.value < 640) return "gap-1.5";
		if (viewportWidth.value < 1024) return "gap-2";
		return "gap-3";
	});

	// Dynamic text sizes
	const dynamicTextSize = computed(() => {
		const width = viewportWidth.value;
		const height = viewportHeight.value;

		// Very small phones
		if (width < 360 || height < 550) {
			return {
				header: "text-[10px]",
				body: "text-[10px]",
				amount: "text-base",
				grandTotal: "text-base",
			};
		}
		// Small phones
		if (width < 640) {
			return {
				header: "text-xs",
				body: "text-xs",
				amount: "text-lg",
				grandTotal: "text-lg",
			};
		}
		// Tablet and typical POS-height screens
		if (height < 800) {
			return {
				header: "text-sm",
				body: "text-sm",
				amount: "text-lg",
				grandTotal: "text-xl",
			};
		}
		// Default desktop
		return {
			header: "text-sm",
			body: "text-sm",
			amount: "text-xl",
			grandTotal: "text-2xl",
		};
	});

	// Dynamic button heights
	const dynamicButtonHeight = computed(() => {
		const width = viewportWidth.value;
		const height = viewportHeight.value;

		// Very small phones - smaller buttons
		if (width < 360 || height < 550) return "h-9";
		// Small phones
		if (width < 640) return "h-10";
		// Short / standard POS screens
		if (height < 800) return "h-10";
		return "h-12";
	});

	// Mobile action button sizing
	const mobileButtonSize = computed(() => {
		const width = viewportWidth.value;
		const height = viewportHeight.value;

		if (width < 360 || height < 550) {
			return {
				height: "h-9",
				text: "text-xs",
				icon: "w-3.5 h-3.5",
				gap: "gap-1",
			};
		}
		if (width < 640) {
			return {
				height: "h-10",
				text: "text-sm",
				icon: "w-4 h-4",
				gap: "gap-1.5",
			};
		}
		return {
			height: "h-11",
			text: "text-sm",
			icon: "w-4 h-4",
			gap: "gap-2",
		};
	});

	// Dynamic numpad key size
	const dynamicNumpadSize = computed(() => {
		if (viewportHeight.value < 600) return { key: "h-9", addBtn: "h-[6rem]" };
		if (viewportHeight.value < 800) return { key: "h-10", addBtn: "h-[7rem]" };
		return { key: "h-11", addBtn: "h-[8rem]" };
	});

	return {
		// State
		viewportWidth,
		viewportHeight,

		// Computed
		dynamicDialogSize,
		isMobileView,
		dialogContentMaxHeight,
		dynamicLeftColumnHeight,
		isCompactMode,
		isSmallMobile,
		dynamicGap,
		dynamicTextSize,
		dynamicButtonHeight,
		mobileButtonSize,
		dynamicNumpadSize,
	};
}
