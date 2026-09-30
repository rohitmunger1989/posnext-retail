# Customer Display — Idle Text Overlay (incremental)

This update is for existing Welcome / Image / Video idle modes only. Do not apply the separate Advertisement Manager patch first.

In Desk POS Settings (or POS Settings UI), enable Customer Display, then Enable Idle Text Overlay. Configure message, Static/Scrolling, Show On (All/Welcome/Image/Video), Top/Bottom/Center, colors, background opacity 0-100, font size 14-72 and scrolling speed. Save. Reopen display if settings do not reload promptly.

Overlay is idle-only and will not show over CART, PAYMENT, RETURN, EXCHANGE or THANK_YOU. Full-screen checkout behavior, cart recovery and cashier functions are unchanged. With Show On = All it applies to each existing mode; it does not create a playlist.

Install: git apply --check PATCH_NAME; git apply PATCH_NAME; bench --site erp.bm-kw.com migrate; bench build --app pos_next; bench --site erp.bm-kw.com clear-cache; bench restart.

If the patch check fails, do not force it. Provide current CustomerDisplay.vue and POS Settings files for rebasing.
