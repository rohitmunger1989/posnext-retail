"""Server-signed POSNext offline authorization."""

import base64
import json
import time
from pathlib import Path

import frappe
from cryptography.hazmat.primitives import serialization

EXPECTED_SITE = "erp.bm-kw.com"
VALIDITY_SECONDS = 72 * 60 * 60

KEY_DIRECTORY = Path(
    "/home/frappe/frappe-bench/sites/private/offline_auth"
)


def encode_base64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@frappe.whitelist()
def issue_offline_authorization():
    """Issue a 72-hour authorization for the authenticated POS cashier."""

    if frappe.local.site != EXPECTED_SITE:
        frappe.throw("Offline authorization is not enabled for this site")

    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(
            "Authentication required",
            frappe.PermissionError,
        )

    if not frappe.db.get_value("User", user, "enabled"):
        frappe.throw("User account is disabled", frappe.PermissionError)

    now = int(time.time())

    payload = {
        "version": 1,
        "purpose": "posnext_offline_authorization",
        "site": EXPECTED_SITE,
        "user": user,
        "issued_at": now,
        "expires_at": now + VALIDITY_SECONDS,
    }

    private_path = KEY_DIRECTORY / "ed25519_private.pem"
    public_path = KEY_DIRECTORY / "ed25519_public.pem"

    private_key = serialization.load_pem_private_key(
        private_path.read_bytes(),
        password=None,
    )

    public_key = public_path.read_text(encoding="ascii")

    payload_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    signature = private_key.sign(payload_bytes)

    return {
        "payload": encode_base64url(payload_bytes),
        "signature": encode_base64url(signature),
        "algorithm": "Ed25519",
        "public_key": public_key,
    }
