import { call } from "@/utils/apiWrapper";

/**
 * Validate an offline-restored cashier against ERPNext.
 *
 * This must be called only when attempting to return online.
 * A failed network request is not proof of an expired session.
 */
export async function revalidateRestoredSession(expectedUser) {
    if (!expectedUser || expectedUser === "Guest") {
        return { status: "unauthorized" };
    }

    try {
        const response = await call("pos_next.api.auth.get_session_user");
        const serverUser = response?.message || response;

        if (
            typeof serverUser === "string" &&
            serverUser === expectedUser
        ) {
            return { status: "verified", user: serverUser };
        }

        return {
            status: "unauthorized",
            user: typeof serverUser === "string" ? serverUser : null,
        };
    } catch (error) {
        const status = Number(
            error?.status ?? error?.response?.status ?? 0
        );

        if (
            status === 401 ||
            status === 403 ||
            error?.exc_type === "AuthenticationError"
        ) {
            return { status: "unauthorized" };
        }

        return {
            status: "unavailable",
            error: String(error?.message || error),
        };
    }
}
