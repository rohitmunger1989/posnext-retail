# POSNext Retail v1.4.19-retail — Customer Display Core

## Included in this build

- Per-POS-Profile Customer Display settings in POS Settings.
- Individual show/hide controls for company, location, POS number, product image, item name, barcode, quantity, original price, discounts, final price, totals, customer, loyalty, customer credit, payment, balance/change and invoice number.
- Customer-name privacy modes: First Name, Full Name, Masked.
- Dark/Light customer display theme and configurable currency label.
- Idle modes: Welcome, promotional Image, promotional Video.
- Configurable Thank You title/message/duration.
- Always-on second-monitor browser page at `/pos/customer-display?profile=<POS PROFILE>`.
- Local BroadcastChannel + localStorage state transport, so the second monitor continues to update from the cashier browser without depending on server realtime for every cart change.
- Live cart item/price/discount/total display.
- Live payment method, paid, remaining and change updates from PaymentDialog.
- Completed-sale Thank You state preserved after the cashier cart is cleared.
- Return and Exchange display states.
- Disabled/hidden customer-sensitive fields are not copied into the customer-display payload.

## Deliberately not included yet

- Android pairing/device-token backend (planned v1.4.20-retail).
- Local Agent serial/COM bridge and pole-display protocols (planned v1.4.21-retail).
- Multi-image/video playlist scheduling.

## Migration/build notes

After deploying the updated app source:

```bash
cd ~/frappe-bench
bench --site <your-site> migrate
bench build --app pos_next
bench --site <your-site> clear-cache
bench restart
```

Then open POS Settings for the required POS Profile, select **Customer Display**, enable it, configure the visible fields, save, and click **Open Customer Display**. Move that browser window to monitor 2 and use its fullscreen button if desired.
