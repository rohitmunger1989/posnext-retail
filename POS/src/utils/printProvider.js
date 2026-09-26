import { logger } from "@/utils/logger";
import { getSavedPrinterName, printHTML as qzPrintHTML } from "@/utils/qzTray";
import { printLocalAgentHTML } from "@/utils/localAgent";

const log = logger.create("PrintProvider");

const PROVIDER_KEY = "posnext_print_provider";
const PAPER_WIDTH_KEY = "posnext_print_paper_width";
const RECEIPT_PRINTER_KEY = "posnext_receipt_printer_name";
const TERMINAL_ID_KEY = "posnext_terminal_id";

export const PRINT_PROVIDER_CHANGED_EVENT = "posnext:print-provider-changed";

export const PRINT_PROVIDERS = Object.freeze({
	BROWSER: "browser",
	QZ: "qz",
	LOCAL_AGENT: "local_agent",
	MOBILE_AGENT: "mobile_agent",
});

function notifyPrintProviderChanged() {
	try {
		window.dispatchEvent(new CustomEvent(PRINT_PROVIDER_CHANGED_EVENT));
	} catch {
		// Ignore non-browser environments.
	}
}

export function getPrintProvider() {
	try {
		const value = String(localStorage.getItem(PROVIDER_KEY) || PRINT_PROVIDERS.QZ)
			.trim()
			.toLowerCase();

		if (Object.values(PRINT_PROVIDERS).includes(value)) {
			return value;
		}
	} catch (error) {
		log.warn("Unable to read print provider:", error);
	}

	// Existing terminals keep their current QZ behavior by default.
	return PRINT_PROVIDERS.QZ;
}

export function savePrintProvider(provider) {
	const value = String(provider || "")
		.trim()
		.toLowerCase();

	if (!Object.values(PRINT_PROVIDERS).includes(value)) {
		throw new Error(`Invalid print provider: ${value}`);
	}

	try {
		localStorage.setItem(PROVIDER_KEY, value);
		notifyPrintProviderChanged();
	} catch (error) {
		log.error("Unable to save print provider:", error);
		throw new Error("Could not save the print method on this terminal.");
	}

	return value;
}

export function getPrintPaperWidth() {
	try {
		return Number(localStorage.getItem(PAPER_WIDTH_KEY)) === 58 ? 58 : 80;
	} catch (error) {
		log.warn("Unable to read print paper width:", error);
		return 80;
	}
}

export function savePrintPaperWidth(width) {
	const value = Number(width) === 58 ? 58 : 80;

	try {
		localStorage.setItem(PAPER_WIDTH_KEY, String(value));
		notifyPrintProviderChanged();
	} catch (error) {
		log.error("Unable to save print paper width:", error);
		throw new Error("Could not save the paper width on this terminal.");
	}

	return value;
}

export function getReceiptPrinterName() {
	try {
		return String(localStorage.getItem(RECEIPT_PRINTER_KEY) || "").trim();
	} catch {
		return "";
	}
}

export function saveReceiptPrinterName(printerName) {
	const value = String(printerName || "").trim();
	try {
		localStorage.setItem(RECEIPT_PRINTER_KEY, value);
		notifyPrintProviderChanged();
	} catch (error) {
		log.error("Unable to save receipt printer:", error);
		throw new Error("Could not save the receipt printer on this terminal.");
	}
	return value;
}

export function getPrintTerminalId() {
	try {
		return String(localStorage.getItem(TERMINAL_ID_KEY) || "").trim();
	} catch {
		return "";
	}
}

export function savePrintTerminalId(terminalId) {
	const value = String(terminalId || "").trim();
	try {
		localStorage.setItem(TERMINAL_ID_KEY, value);
		notifyPrintProviderChanged();
	} catch (error) {
		log.error("Unable to save terminal ID:", error);
		throw new Error("Could not save the terminal ID on this device.");
	}
	return value;
}

export function isBrowserPrintProvider() {
	return getPrintProvider() === PRINT_PROVIDERS.BROWSER;
}

export function isQzPrintProvider() {
	return getPrintProvider() === PRINT_PROVIDERS.QZ;
}

export function isLocalAgentPrintProvider() {
	return getPrintProvider() === PRINT_PROVIDERS.LOCAL_AGENT;
}

export function isMobileAgentPrintProvider() {
	return getPrintProvider() === PRINT_PROVIDERS.MOBILE_AGENT;
}

/**
 * Send HTML through the terminal's configured print provider.
 * Browser printing is intentionally returned to printInvoice.js because it
 * requires the normal browser/OS print dialog.
 */
export async function silentPrintHTML(
	html,
	{
		printerName = "",
		terminalId = "",
		jobName = "POSNext Receipt",
	} = {}
) {
	const content = String(html || "");
	if (!content.trim()) throw new Error("Print HTML is empty.");

	const provider = getPrintProvider();
	const terminalPrinter = String(getReceiptPrinterName() || "").trim();
	const configuredPrinter = String(
		printerName ||
			(provider === PRINT_PROVIDERS.QZ ? getSavedPrinterName() : terminalPrinter) ||
			terminalPrinter ||
			""
	).trim();
	const configuredTerminalId = String(terminalId || getPrintTerminalId() || "").trim();
	const paperWidthMm = getPrintPaperWidth();

	log.info(`Printing with provider: ${provider}`);

	switch (provider) {
		case PRINT_PROVIDERS.QZ:
			await qzPrintHTML(content, configuredPrinter || undefined, {
				width: paperWidthMm,
			});
			return { success: true, provider };

		case PRINT_PROVIDERS.LOCAL_AGENT:
			await printLocalAgentHTML(content, {
				printerName: configuredPrinter,
				terminalId: configuredTerminalId,
				paperWidthMm,
				jobName: String(jobName || "POSNext Receipt").trim(),
			});
			return { success: true, provider };

		case PRINT_PROVIDERS.MOBILE_AGENT:
			throw new Error("POSNext Mobile Agent support is not available yet.");

		case PRINT_PROVIDERS.BROWSER:
			return {
				success: false,
				provider,
				browserRequired: true,
			};

		default:
			throw new Error(`Unsupported print provider: ${provider}`);
	}
}
