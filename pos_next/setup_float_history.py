"""Keep the app-shipped Float History report reachable after install and migration."""
import json

import frappe


REPORT = "POS Float History"
LABEL = "Float History"


def _add_workspace_navigation(workspace):
    """Repair only our widgets; preserve every other card, shortcut and content block."""
    before_links = [row.as_dict() for row in workspace.get("links", [])]
    existing = next((dict(row) for row in before_links if row.get("link_to") == REPORT), {})
    links = [dict(row) for row in before_links if row.get("link_to") != REPORT]
    content = json.loads(workspace.content or "[]")
    original_content = json.loads(workspace.content or "[]")
    card = next((i for i, row in enumerate(links) if row.get("type") == "Card Break" and row.get("label") == "Reports"), None)
    if card is None:
        card = len(links)
        links.append({"type": "Card Break", "label": "Reports", "hidden": 0})
        if not any(row.get("type") == "card" and row.get("data", {}).get("card_name") == "Reports" for row in content):
            content.append({"id": "pos-float-reports-card", "type": "card", "data": {"card_name": "Reports", "col": 4}})
    end = next((i for i in range(card + 1, len(links)) if links[i].get("type") == "Card Break"), len(links))
    existing.update({"type": "Link", "label": LABEL, "link_type": "Report", "link_to": REPORT,
        "is_query_report": 1, "report_ref_doctype": "POS Opening Shift", "hidden": 0})
    links.insert(end, existing)
    for i, row in enumerate(links):
        if row.get("type") == "Card Break":
            following = next((j for j in range(i + 1, len(links)) if links[j].get("type") == "Card Break"), len(links))
            row["link_count"] = following - i - 1
    changed = links != before_links
    if workspace.meta.has_field("type") and not workspace.get("type"):
        workspace.type = "Workspace"
        changed = True
    if changed:
        workspace.set("links", links)
    shortcut = next((row for row in workspace.get("shortcuts", []) if row.get("link_to") == REPORT), None)
    if shortcut is None:
        workspace.append("shortcuts", {"type": "Report", "label": LABEL, "link_to": REPORT, "color": "Green"})
        changed = True
    else:
        previous_label = shortcut.label
        if shortcut.label != LABEL or shortcut.type != "Report":
            shortcut.label, shortcut.type = LABEL, "Report"
            for row in content:
                if row.get("type") == "shortcut" and row.get("data", {}).get("shortcut_name") == previous_label:
                    row["data"]["shortcut_name"] = LABEL
            changed = True
    if not any(row.get("type") == "shortcut" and row.get("data", {}).get("shortcut_name") == LABEL for row in content):
        last = next((i for i in range(len(content) - 1, -1, -1) if content[i].get("type") == "shortcut"), -1)
        block = {"id": "pos-float-history-shortcut", "type": "shortcut", "data": {"shortcut_name": LABEL, "col": 3}}
        content.insert(last + 1, block) if last >= 0 else content.append(block)
    if content != original_content:
        workspace.content = json.dumps(content)
        changed = True
    if changed:
        workspace.flags.with_module = True
        workspace.save(ignore_permissions=True)
    return changed




def _ensure_pos_user_pin_navigation(workspace):
    """Add the PIN list under Configuration, preserving other workspace links."""
    before = [r.as_dict() for r in workspace.get("links", [])]
    data = {"links": [dict(r) for r in before]}
    links = data["links"]
    links[:] = [r for r in links if r.get("link_to") != "POS User PIN"]
    start = next((i for i,r in enumerate(links) if r.get("type") == "Card Break" and r.get("label") == "Configuration"), None)
    if start is None:
        return
    end = next((i for i in range(start+1,len(links)) if links[i].get("type") == "Card Break"),len(links))
    links.insert(end, {"type":"Link","label":"POS User PIN","link_type":"DocType","link_to":"POS User PIN","hidden":0,"onboard":0,"is_query_report":0})
    for i,row in enumerate(links):
        if row.get("type") == "Card Break":
            end = next((j for j in range(i+1,len(links)) if links[j].get("type") == "Card Break"),len(links))
            row["link_count"] = end-i-1
    if links != before:
        workspace.set("links",links)
        if workspace.meta.has_field("type") and not workspace.get("type"):
            workspace.type = "Workspace"
        workspace.flags.with_module = True
        workspace.save(ignore_permissions=True)


def ensure_float_history_workspace():
    """Existing hooks call this on both fresh installs and upgrades.

    Sidebar uses Frappe's supported file importer, so no developer-mode/manual
    Sidebar editing is needed on the installed site. Custom Sidebar overlays
    are left intact. The report and workspace files remain in the app for the
    next fresh installation.
    """
    if not frappe.db.exists("Report", REPORT):
        frappe.reload_doc("pos_next", "report", "pos_float_history", force=True)
    if not frappe.db.exists("Workspace", "POSNext"):
        frappe.reload_doc("pos_next", "workspace", "posnext", force=True)
    workspace = frappe.get_doc("Workspace", "POSNext")
    _add_workspace_navigation(workspace)
    _ensure_pos_user_pin_navigation(workspace)
    # Frappe v16.52+ supports module-owned standard Sidebar JSON.
    if frappe.db.exists("DocType", "Sidebar"):
        frappe.reload_doc("pos_next", "sidebar", "pos_next", force=True)
    frappe.clear_cache()
