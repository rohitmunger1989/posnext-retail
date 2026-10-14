/**
 * POSNext Retail — Offline Authorization
 * v1.4.25 development
 *
 * Local authorization metadata only.
 * A cached username or timestamp must not independently grant access.
 */

const STORAGE_KEY = "pos_offline_authorization_v1";
const VALIDITY_MS = 72 * 60 * 60 * 1000;

export function getOfflineAuthorization() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;

        const data = JSON.parse(raw);

        if (
            !data ||
            typeof data.user !== "string" ||
            !Number.isFinite(data.verifiedAt) ||
            !Number.isFinite(data.expiresAt)
        ) {
            return null;
        }

        const now = Date.now();

        if (
            data.verifiedAt > now ||
            data.expiresAt <= now ||
            data.expiresAt - data.verifiedAt > VALIDITY_MS
        ) {
            return null;
        }

        return data;
    } catch {
        return null;
    }
}

export function recordOfflineAuthorization(user) {
    if (!user || user === "Guest") {
        throw new Error("Valid authenticated user required");
    }

    const verifiedAt = Date.now();

    const data = {
        user,
        verifiedAt,
        expiresAt: verifiedAt + VALIDITY_MS,
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));

    return data;
}

export function revokeOfflineAuthorization() {
    localStorage.removeItem(STORAGE_KEY);
}

export const OFFLINE_AUTHORIZATION_VALIDITY_MS = VALIDITY_MS;

/**
 * Persist a server-issued signed token.
 * Token validation is performed separately before granting access.
 */
export function storeSignedOfflineAuthorization(token) {
    if (
        !token ||
        token.algorithm !== "Ed25519" ||
        typeof token.payload !== "string" ||
        typeof token.signature !== "string"
    ) {
        throw new Error("Invalid offline authorization token");
    }

    localStorage.setItem(
        "pos_offline_signed_authorization_v1",
        JSON.stringify({
            algorithm: token.algorithm,
            payload: token.payload,
            signature: token.signature,
        })
    );
}

export function getSignedOfflineAuthorization() {
    try {
        const raw = localStorage.getItem(
            "pos_offline_signed_authorization_v1"
        );
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}


// Prevent delayed server responses from restoring tokens after logout.
// This counter is intentionally in memory; it resets on page reload.
let authorizationGeneration = 0;

export function beginOfflineAuthorizationRequest() {
    authorizationGeneration += 1;
    return authorizationGeneration;
}

export function isOfflineAuthorizationRequestCurrent(generation) {
    return generation === authorizationGeneration;
}

export function invalidateOfflineAuthorizationRequests() {
    authorizationGeneration += 1;
}

/** Refresh a server-signed offline grant after a confirmed online login/session. */
export async function refreshSignedOfflineAuthorization(user) {
    if (!user || user === "Guest") return false;
    const generation = beginOfflineAuthorizationRequest();
    try {
        const [{ call }, { verifyOfflineAuthorization }] = await Promise.all([
            import("@/utils/apiWrapper"),
            import("./verifyOfflineAuthorization"),
        ]);
        const response = await call("pos_next.api.offline_authorization.issue_offline_authorization");
        const token = response?.message || response;
        if (!isOfflineAuthorizationRequestCurrent(generation)) return false;
        if (!await verifyOfflineAuthorization(token, user)) return false;
        if (!isOfflineAuthorizationRequestCurrent(generation)) return false;
        storeSignedOfflineAuthorization(token);
        return true;
    } catch (error) {
        console.warn("Could not refresh signed offline authorization:", error);
        return false;
    }
}
