import { ref, watch, nextTick, onMounted, onUnmounted } from "vue";
import { QueuedMutex } from "@/utils/mutex";
import { usePOSSettingsStore } from "@/stores/posSettings";
import { playScanError, playScanSuccess } from "@/utils/scannerSound";

/**
 * Composable for search input, barcode scanning, and auto-add logic.
 *
 * Owns all search-input state, timers, and event handlers with proper
 * concurrency control.  Extracted from ItemsSelector.vue.
 *
 * Concurrency model:
 *   - On Enter (or auto-add timeout), the barcode is **snapshotted** from the
 *     DOM input immediately, then the input is cleared so the next scan starts
 *     into a clean field.
 *   - The snapshot is pushed into a {@link QueuedMutex}-backed queue
 *     (`processBarcodeScan`), which processes barcode lookups sequentially.
 *   - This guarantees no barcode is ever lost, even when scanning different
 *     items faster than the API can respond (~50 ms between scans).
 *
 * @param {Object} options
 * @param {Object} options.itemStore          - Pinia item-search store
 * @param {(item: Object, autoAdd: boolean) => boolean} options.onItemFound
 *        Component's selectItem(). Returns true if item was accepted.
 * @param {Object} options.showWarning        - useToast().showWarning
 * @param {import('vue').Ref<boolean>} options.isAnyDialogOpen
 */
export function useSearchInput({ itemStore, onItemFound, showWarning, isAnyDialogOpen }) {
        const posSettingsStore = usePOSSettingsStore();

	// --- Reactive state (exposed) ---
	const searchInputRef = ref(null);
	const scannerEnabled = ref(true);
	const autoAddEnabled = ref(true);

	// --- Internal (non-reactive) ---
	let autoSearchTimer = null;
	const barcodeQueue = new QueuedMutex({ timeout: 10000, name: "BarcodeSearch" });

	// -------------------------------------------------------------------------
	// Persistent barcode scanner focus
	// -------------------------------------------------------------------------

	function isTextEntryElement(element) {
		if (!element || element === document.body) return false;
		if (element === searchInputRef.value) return false;

		return Boolean(
			element.matches?.(
				'input, textarea, select, [contenteditable="true"], [contenteditable=""]'
			)
		);
	}

	function restoreScannerFocus() {
		if (!scannerEnabled.value) return;
		if (isAnyDialogOpen?.value) return;
		if (document.hidden) return;

		// Do not steal focus while the cashier is deliberately typing
		// into another form field.
		if (isTextEntryElement(document.activeElement)) return;

		nextTick(() => {
			if (!scannerEnabled.value) return;
			if (isAnyDialogOpen?.value) return;
			if (document.hidden) return;
			if (isTextEntryElement(document.activeElement)) return;

			focusSearchInput();
		});
	}

	function queueScannerFocus() {
		window.setTimeout(() => {
			restoreScannerFocus();
		}, 0);
	}

	function handleScannerWindowFocus() {
		queueScannerFocus();
	}

	function handleScannerVisibilityChange() {
		if (!document.hidden) {
			queueScannerFocus();
		}
	}

	function handleScannerPointerUp() {
		queueScannerFocus();
	}

	onMounted(() => {
		window.addEventListener("focus", handleScannerWindowFocus);
		document.addEventListener(
			"visibilitychange",
			handleScannerVisibilityChange
		);
		document.addEventListener(
			"pointerup",
			handleScannerPointerUp,
			true
		);

		// Initial POS load / browser refresh.
		queueScannerFocus();
	});

	// When a payment/customer/return/etc. dialog closes,
	// immediately return the scanner cursor to the search field.
	watch(
		() => Boolean(isAnyDialogOpen?.value),
		(isOpen, wasOpen) => {
			if (wasOpen && !isOpen) {
				queueScannerFocus();
			}
		}
	);

	onUnmounted(() => {
		window.removeEventListener("focus", handleScannerWindowFocus);
		document.removeEventListener(
			"visibilitychange",
			handleScannerVisibilityChange
		);
		document.removeEventListener(
			"pointerup",
			handleScannerPointerUp,
			true
		);
	});


	// ---- Timer helpers ----

	function clearAutoSearchTimer() {
		if (autoSearchTimer) {
			clearTimeout(autoSearchTimer);
			autoSearchTimer = null;
		}
	}

	// ---- Focus ----

	function focusSearchInput() {
		nextTick(() => {
			if (searchInputRef.value) {
				searchInputRef.value.focus();
			}
		});
	}

	// ---- Clear ----

	/** Atomic clear: timer -> store -> DOM input.value -> refocus */
	function clearSearchAndResetInput() {
		clearAutoSearchTimer();
		itemStore.clearSearch();
		if (searchInputRef.value) {
			searchInputRef.value.value = "";
		}
		if (scannerEnabled.value || autoAddEnabled.value) {
			focusSearchInput();
		}
	}

	// ---- Event handlers ----

	function handleKeyDown(event) {
		if (event.key === "Enter") {
			event.preventDefault();
			clearAutoSearchTimer();

			// Snapshot the barcode NOW from the DOM input, before anything overwrites it
			const barcode = searchInputRef.value?.value?.trim() || itemStore.searchTerm?.trim();
			if (barcode) {
				// Clear input immediately so next scan starts clean
				itemStore.clearSearch();
				if (searchInputRef.value) searchInputRef.value.value = "";

				// Queue the search with the captured barcode
				processBarcodeScan(barcode, autoAddEnabled.value);
			}
			return;
		}
		// All other keys: no special handling needed.
		// Dead scanner-speed-detection code removed.
	}

	/**
	 * Handles the `input` event on the search <input>.
	 *
	 * Two independent timers exist by design:
	 *   1. itemStore.setSearchTerm() triggers the store's own debounce for
	 *      updating the displayed item grid.
	 *   2. autoSearchTimer (500 ms) triggers auto-add behaviour — completely
	 *      separate from display.
	 */
	function handleSearchInput(event) {
		const value = event.target.value;

		// Guard: ignore stale empty events after search was already cleared
		if (!value && !itemStore.searchTerm) {
			return;
		}

		itemStore.setSearchTerm(value);

		clearAutoSearchTimer();

		// Auto-add: after user stops typing for 500 ms, trigger barcode search
		if (autoAddEnabled.value && value.trim().length > 0) {
			autoSearchTimer = setTimeout(() => {
				const barcode =
					searchInputRef.value?.value?.trim() || itemStore.searchTerm?.trim();
				if (barcode) {
					itemStore.clearSearch();
					if (searchInputRef.value) searchInputRef.value.value = "";
					processBarcodeScan(barcode, true);
				}
			}, 500);
		}
	}

	/** Clicking the search input clears search + timer atomically. */
	function handleSearchClick() {
		clearSearchAndResetInput();
	}

	/**
	 * Queue a barcode scan for sequential processing.
	 *
	 * The barcode string is already captured (snapshotted) by the caller —
	 * it is never read from shared state here. The {@link QueuedMutex}
	 * ensures scans execute one at a time so every scan is resolved before
	 * the next begins, preventing double-adds and lost barcodes.
	 *
	 * Lookup: exact barcode match via `itemStore.searchByBarcode()`.
	 * If the barcode is not found, shows a "not found" warning.
	 *
	 * @param {string}  barcode      - Pre-captured barcode value
	 * @param {boolean} forceAutoAdd - When true, item is added without user click
	 */
	function processBarcodeScan(barcode, forceAutoAdd) {
		const shouldAutoAdd = forceAutoAdd || (scannerEnabled.value && autoAddEnabled.value);

		barcodeQueue.withLock(async () => {
			try {
				const item = await itemStore.searchByBarcode(barcode);
				if (item) {
					const accepted = onItemFound(item, shouldAutoAdd);

					if (accepted !== false) {
						playScanSuccess({
							enabled: posSettingsStore.enableScanSounds,
							soundEnabled: posSettingsStore.enableScanSuccessSound,
							volume: posSettingsStore.scanSuccessVolume,
						});
					}

					focusSearchInput();
					return;
				}
			} catch (error) {
				console.error("Barcode API error:", error);
			}

			// Barcode not found — show clear "not found" message.
			// Note: we cannot fall back to filteredItems here because
			// clearSearch() was called before the API request, so
			// filteredItems would contain ALL cached items (not search results).
			playScanError({
					enabled: posSettingsStore.enableScanSounds,
					soundEnabled: posSettingsStore.enableScanErrorSound,
					volume: posSettingsStore.scanErrorVolume,
				});
			showWarning(__("Item Not Found: No item found with barcode: {0}", [barcode]));
			focusSearchInput();
		});
	}

	// ---- Toggles ----

	function toggleBarcodeScanner() {
		scannerEnabled.value = !scannerEnabled.value;

		if (scannerEnabled.value) {
			autoAddEnabled.value = true;
			focusSearchInput();
		} else {
			autoAddEnabled.value = false;
		}
	}

	function toggleAutoAdd() {
		autoAddEnabled.value = !autoAddEnabled.value;

		if (autoAddEnabled.value && !scannerEnabled.value) {
			scannerEnabled.value = true;
		}

		if (!autoAddEnabled.value) {
			clearAutoSearchTimer();
		}

		if (autoAddEnabled.value) {
			focusSearchInput();
		}
	}

	// ---- Dialog-close watcher ----
	// Refocuses the search bar when all dialogs close (scanner/auto-add modes)
	const stopDialogWatcher = watch(isAnyDialogOpen, (isOpen, wasOpen) => {
		if (wasOpen && !isOpen && (scannerEnabled.value || autoAddEnabled.value)) {
			focusSearchInput();
		}
	});

	// ---- Cleanup ----
	function cleanup() {
		clearAutoSearchTimer();
		stopDialogWatcher();
	}

	onUnmounted(cleanup);

	return {
		// State
		searchInputRef,
		scannerEnabled,
		autoAddEnabled,

		// Event handlers
		handleSearchInput,
		handleKeyDown,
		handleSearchClick,

		// Toggles
		toggleBarcodeScanner,
		toggleAutoAdd,

		// Utilities
		focusSearchInput,
		clearSearchAndResetInput,
		cleanup,
	};
}
