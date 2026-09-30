# POSNext Customer Display - Terminal Identity Update

Terminal identity now uses the existing **Printer & Cash Drawer Setup → Terminal ID** as the single source of truth for each physical POS workstation.

Priority:

1. Printer & Cash Drawer Setup Terminal ID (`posnext_terminal_id`)
2. POSNext Local Agent Terminal ID, only as a compatibility fallback
3. Auto-generated browser ID, only when neither is configured

Customer Display settings no longer contain a separate terminal-ID editor. The same workstation Terminal ID will be reused by Browser Customer Display, Android pairing, and COM/Serial display support.

Customer display channels and snapshots remain isolated by `POS Profile + Terminal ID`.


## Header / payment / customer-search stability update
- Customer Display header now uses the Company master `company_logo` when available.
- Paid / Change Due / Remaining tiles use direct rendered styles so their colors work reliably in both light and dark themes.
- Customer search captures Enter while focused so the key press cannot leak into other POS keyboard/scanner handlers.
