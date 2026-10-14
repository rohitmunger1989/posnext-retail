import { OFFLINE_AUTH_PUBLIC_KEY } from "./offlinePublicKey";

const EXPECTED_SITE = "erp.bm-kw.com";
const EXPECTED_PURPOSE = "posnext_offline_authorization";
const MAX_VALIDITY_SECONDS = 72 * 60 * 60;

function decodeBase64Url(value) {
    if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) {
        throw new Error("Invalid authorization encoding");
    }

    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const binary = atob(padded);

    return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

export async function verifyOfflineAuthorization(token, expectedUser) {
    try {
        if (
            !globalThis.crypto?.subtle ||
            !token ||
            token.algorithm !== "Ed25519" ||
            !expectedUser ||
            expectedUser === "Guest"
        ) {
            return false;
        }

        const publicKeyBytes = decodeBase64Url(OFFLINE_AUTH_PUBLIC_KEY);
        const payloadBytes = decodeBase64Url(token.payload);
        const signatureBytes = decodeBase64Url(token.signature);

        const key = await crypto.subtle.importKey(
            "raw",
            publicKeyBytes,
            { name: "Ed25519" },
            false,
            ["verify"]
        );

        const validSignature = await crypto.subtle.verify(
            "Ed25519",
            key,
            signatureBytes,
            payloadBytes
        );

        if (!validSignature) return false;

        const payload = JSON.parse(
            new TextDecoder("utf-8", { fatal: true }).decode(payloadBytes)
        );

        const now = Math.floor(Date.now() / 1000);

        return (
            payload.version === 1 &&
            payload.purpose === EXPECTED_PURPOSE &&
            payload.site === EXPECTED_SITE &&
            payload.user === expectedUser &&
            Number.isSafeInteger(payload.issued_at) &&
            Number.isSafeInteger(payload.expires_at) &&
            payload.issued_at <= now &&
            payload.expires_at > now &&
            payload.expires_at > payload.issued_at &&
            payload.expires_at - payload.issued_at <= MAX_VALIDITY_SECONDS
        );
    } catch (error) {
        console.warn("Offline authorization verification failed:", error);
        return false;
    }
}
