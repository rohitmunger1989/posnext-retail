import { logger } from "@/utils/logger";

const log = logger.create("POSNextMobileAgent");
const DEFAULT_AGENT_URL = "http://127.0.0.1:17778";
const AGENT_URL_KEY = "posnext_mobile_agent_url";
const AGENT_TOKEN_KEY = "posnext_mobile_agent_token";

const MOBILE_AGENT_TEST_PDF_BASE64 = "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCAyMjYuNzcgMTgwXSAvUmVzb3VyY2VzIDw8IC9Gb250IDw8IC9GMSA1IDAgUiA+PiA+PiAvQ29udGVudHMgNCAwIFIgPj4KZW5kb2JqCjQgMCBvYmoKPDwgL0xlbmd0aCAxNDEgPj4Kc3RyZWFtCkJUIC9GMSAxNiBUZiAxOCAxNTAgVGQgKFBPU05leHQgUERGIFRlc3QpIFRqIDAgLTI2IFRkIC9GMSAxMSBUZiAoRVJQIEJyb3dzZXIgLT4gTW9iaWxlIEFnZW50IC0+IEVTQy9QT1MpIFRqIDAgLTIwIFRkICg4MG1tIFBERiBwYXRoIE9LKSBUaiBFVAplbmRzdHJlYW0KZW5kb2JqCjUgMCBvYmoKPDwgL1R5cGUgL0ZvbnQgL1N1YnR5cGUgL1R5cGUxIC9CYXNlRm9udCAvSGVsdmV0aWNhID4+CmVuZG9iagp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA2NCAwMDAwMCBuIAowMDAwMDAwMTIxIDAwMDAwIG4gCjAwMDAwMDAyNTAgMDAwMDAgbiAKMDAwMDAwMDQ0MiAwMDAwMCBuIAp0cmFpbGVyCjw8IC9TaXplIDYgL1Jvb3QgMSAwIFIgPj4Kc3RhcnR4cmVmCjUxMgolJUVPRgo=";

export function getMobileAgentUrl() {
	try {
		return String(localStorage.getItem(AGENT_URL_KEY) || DEFAULT_AGENT_URL).replace(/\/+$/, "");
	} catch {
		return DEFAULT_AGENT_URL;
	}
}

export function getMobileAgentToken() {
	try {
		return String(localStorage.getItem(AGENT_TOKEN_KEY) || "").trim();
	} catch {
		return "";
	}
}

export function saveMobileAgentToken(token) {
	try {
		localStorage.setItem(AGENT_TOKEN_KEY, String(token || "").trim());
	} catch (error) {
		log.warn("Unable to save Mobile Agent token:", error);
	}
}

function createNonce() {
	if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
	const bytes = new Uint8Array(16);
	globalThis.crypto?.getRandomValues?.(bytes);
	return `posnext-${Date.now()}-${Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("")}`;
}

async function agentRequest(path, { method = "GET", body = null, timeoutMs = 5000 } = {}) {
	const token = getMobileAgentToken();
	if (!token) {
		throw new Error("POSNext Mobile Agent token is not configured on this terminal.");
	}

	const controller = new AbortController();
	const timer = window.setTimeout(() => controller.abort(), timeoutMs);
	try {
		const response = await fetch(`${getMobileAgentUrl()}${path}`, {
			method,
			headers: {
				"Content-Type": "application/json",
				"X-POSNext-Token": token,
				"X-POSNext-Nonce": createNonce(),
			},
			body: body == null ? undefined : JSON.stringify(body),
			signal: controller.signal,
			cache: "no-store",
		});

		const payload = await response.json().catch(() => ({}));
		if (!response.ok || payload?.success === false) {
			throw new Error(payload?.message || `POSNext Mobile Agent request failed (${response.status})`);
		}
		return payload;
	} catch (error) {
		if (error?.name === "AbortError") {
			throw new Error("POSNext Mobile Agent did not respond in time.");
		}
		if (error instanceof TypeError) {
			throw new Error(
				"Could not reach POSNext Mobile Agent on this device. Check that the Android agent is running and its ERPNext Origin matches this POS URL."
			);
		}
		throw error;
	} finally {
		window.clearTimeout(timer);
	}
}

export async function mobileAgentHealth() {
	return agentRequest("/health", { timeoutMs: 2500 });
}

export async function listMobileAgentPrinters() {
	const result = await agentRequest("/printers", { timeoutMs: 5000 });
	return Array.isArray(result?.printers) ? result.printers : [];
}

export async function testMobileAgentPrinter(printerName = "", terminalId = "") {
	return agentRequest("/test-print", {
		method: "POST",
		body: {
			printer_name: String(printerName || "").trim() || null,
			terminal_id: String(terminalId || "").trim(),
		},
		timeoutMs: 12000,
	});
}

async function pdfDataToBase64(pdfData) {
	if (typeof pdfData === "string") {
		const value = pdfData.trim();
		if (!value) throw new Error("Mobile Agent PDF is empty.");
		const marker = "base64,";
		const markerIndex = value.indexOf(marker);
		return markerIndex >= 0 ? value.slice(markerIndex + marker.length) : value;
	}

	let bytes;
	if (pdfData instanceof Blob) {
		bytes = new Uint8Array(await pdfData.arrayBuffer());
	} else if (pdfData instanceof ArrayBuffer) {
		bytes = new Uint8Array(pdfData);
	} else if (ArrayBuffer.isView(pdfData)) {
		bytes = new Uint8Array(pdfData.buffer, pdfData.byteOffset, pdfData.byteLength);
	} else {
		throw new Error("Unsupported Mobile Agent PDF data.");
	}

	if (!bytes.length) throw new Error("Mobile Agent PDF is empty.");

	let binary = "";
	const chunkSize = 0x8000;
	for (let offset = 0; offset < bytes.length; offset += chunkSize) {
		binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
	}
	return btoa(binary);
}

export async function printMobileAgentPDF(
	pdfData,
	{
		printerName = "",
		terminalId = "",
		paperWidthMm = 80,
		jobName = "POSNext Receipt",
		cutTiming = "after_document",
		cutMode = "partial",
	} = {}
) {
	const pdfBase64 = await pdfDataToBase64(pdfData);

	return agentRequest("/print/pdf", {
		method: "POST",
		body: {
			printer_name: String(printerName || "").trim() || null,
			terminal_id: String(terminalId || "").trim(),
			pdf_base64: pdfBase64,
			job_name: String(jobName || "POSNext Receipt").trim(),
			paper_width_mm: Number(paperWidthMm) === 58 ? 58 : 80,
			cut_timing: ["none", "after_document", "after_page"].includes(String(cutTiming || ""))
				? String(cutTiming)
				: "after_document",
			cut_mode: String(cutMode || "").trim().toLowerCase() === "full" ? "full" : "partial",
		},
		timeoutMs: 90000,
	});
}

export async function testMobileAgentPDF(
	printerName = "",
	terminalId = "",
	paperWidthMm = 80,
	cutTiming = "after_document",
	cutMode = "partial"
) {
	return printMobileAgentPDF(MOBILE_AGENT_TEST_PDF_BASE64, {
		printerName,
		terminalId,
		paperWidthMm,
		jobName: "POSNext PDF Receipt Test",
		cutTiming,
		cutMode,
	});
}

export async function testMobileAgentPaperCut(cutMode = "partial") {
	const mode = String(cutMode || "partial").trim().toLowerCase() === "full" ? "full" : "partial";
	return agentRequest("/paper/cut", {
		method: "POST",
		body: { cut_mode: mode },
		timeoutMs: 8000,
	});
}

export async function openMobileAgentCashDrawer(
	printerName = "",
	commandProfile = "escpos_drawer_1",
	terminalId = ""
) {
	try {
		const result = await agentRequest("/drawer/open", {
			method: "POST",
			body: {
				printer_name: String(printerName || "").trim() || null,
				command_profile: commandProfile,
				terminal_id: String(terminalId || "").trim(),
			},
			timeoutMs: 8000,
		});
		return { success: true, printerName: String(printerName || "").trim(), ...result };
	} catch (error) {
		log.error("Mobile Agent drawer open failed:", error);
		throw error;
	}
}

export async function printMobileAgentHTML(
	html,
	{
		printerName = "",
		terminalId = "",
		paperWidthMm = 80,
		jobName = "POSNext Receipt",
		cutTiming = "after_document",
		cutMode = "partial",
	} = {}
) {
	const content = String(html || "");
	if (!content.trim()) {
		throw new Error("Mobile Agent print HTML is empty.");
	}

	return agentRequest("/print/html", {
		method: "POST",
		body: {
			printer_name: String(printerName || "").trim() || null,
			terminal_id: String(terminalId || "").trim(),
			html: content,
			job_name: String(jobName || "POSNext Receipt").trim(),
			paper_width_mm: Number(paperWidthMm) === 58 ? 58 : 80,
			base_url: typeof window !== "undefined" ? window.location.origin : "",
			cut_timing: ["none", "after_document", "after_page"].includes(String(cutTiming || ""))
				? String(cutTiming)
				: "after_document",
			cut_mode: String(cutMode || "").trim().toLowerCase() === "full" ? "full" : "partial",
		},
		timeoutMs: 30000,
	});
}
