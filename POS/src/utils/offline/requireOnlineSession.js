import { session } from "@/data/session";
import { offlineState } from "@/utils/offline/offlineState";
import { revalidateRestoredSession } from "./revalidateSession";

let validationPromise = null;

/**
 * Prevent server-side POS operations from using an
 * offline-restored session without ERPNext authentication.
 */
export async function requireOnlineSession() {
    if (offlineState.isOffline) {
        throw new Error("ERPNext is offline. Online operation blocked.");
    }

    if (!session.user || session.user === "Guest") {
        throw new Error("ERPNext login required.");
    }

    if (!session.offlineRestored) {
        return true;
    }

    if (!validationPromise) {
        const expectedUser = session.user;

        const pending = (async () => {
            const result = await revalidateRestoredSession(expectedUser);

            if (result.status !== "verified") {
                throw new Error(
                    result.status === "unauthorized"
                        ? "ERPNext session expired or changed. Login required."
                        : "ERPNext authentication unavailable. Please retry."
                );
            }

            if (
                session.user !== expectedUser ||
                !session.offlineRestored
            ) {
                throw new Error("POS session changed during verification.");
            }

            session.offlineRestored = false;
            return true;
        })();

        validationPromise = pending;

        void pending.finally(() => {
            if (validationPromise === pending) {
                validationPromise = null;
            }
        }).catch(() => {});
    }

    return await validationPromise;
}
