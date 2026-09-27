import { silentPrintDoc } from "./printInvoice";
import { getPrintProvider, PRINT_PROVIDERS } from "./printProvider";

const EOD_PRINT_FORMAT = "POS Next EOD Report";
const EOD_DOCTYPE = "POS Closing Shift";

export async function printEODReport(closingShiftName) {
        const name = String(closingShiftName || "").trim();

        if (!name) {
                throw new Error("Closing shift name is required for EOD printing.");
        }

        const provider = getPrintProvider();

        // Browser printing uses Frappe's normal print view so the
        // browser/OS print dialog can handle the document.
        if (provider === PRINT_PROVIDERS.BROWSER) {
                const params = new URLSearchParams({
                        doctype: EOD_DOCTYPE,
                        name,
                        format: EOD_PRINT_FORMAT,
                        no_letterhead: "1",
                        _lang: "en",
                        trigger_print: "1",
                        _t: String(Date.now()),
                });

                const printWindow = window.open(
                        `/printview?${params.toString()}`,
                        "_blank",
                        "width=800,height=600"
                );

                if (!printWindow) {
                        throw new Error("Popup blocked — check your browser settings.");
                }

                return true;
        }

        // QZ Tray, Local Agent and Mobile Agent use the common
        // terminal print-provider routing.
        await silentPrintDoc(
                EOD_DOCTYPE,
                name,
                EOD_PRINT_FORMAT
        );

        return true;
}
