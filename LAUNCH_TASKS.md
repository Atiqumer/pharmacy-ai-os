# RxOS LinkedIn Launch Board

**Target:** public product demonstration this week  
**Release scope:** one pharmacy owner, one pharmacy, production-like demo data

## P0 — must pass before recording or going live

- [x] Reduce API latency on warm Vercel instances by reusing PostgreSQL connections.
  - Acceptance: connections are pooled safely, returned after every request, and backend tests pass.
- [x] Make the AI expiry briefing use the pharmacy's configured warning window and exact days remaining.
  - Acceptance: no hard-coded 90-day claim and no invented expiry timing.
- [x] Return unambiguous UTC timestamps from the API.
  - Acceptance: sales, returns, purchases, stock movements, suppliers, users, and settings serialize datetimes as ISO 8601 UTC.
- [x] Refresh low-stock and expiry alerts immediately after inventory changes.
  - Acceptance: create/import/adjust/receive/sale/return actions update the notification badge without waiting two minutes.
- [x] Give report downloads visible progress, success, and error feedback.
  - Acceptance: duplicate clicks are prevented while downloading and the user receives a clear result.
- [x] Run backend tests, frontend lint, and frontend production build.
  - Verified locally: 63 backend tests passed, 2 live PostgreSQL tests skipped, frontend lint passed, and the Next.js production build passed.
- [ ] Deploy and repeat the complete production workflow with clean demo data.

## P1 — demo quality

- [x] Prepare a small, realistic demo inventory CSV.
- [x] Write a one-page demo/operator guide and a 3–5 minute LinkedIn demo script.
- [ ] Verify desktop, tablet, and mobile layouts on Chrome/Edge.
- [ ] Add browser automation for login → inventory → purchase → sale → return → alert.
- [ ] Add basic uptime/error monitoring for the public frontend and API.

## P2 — validate with the pharmacy before building

- [ ] Test Aronium-compatible product/inventory import using an anonymized export.
- [ ] Confirm whether barcode-scanner input is required for daily checkout.
- [ ] Confirm which printable documents are essential: sales receipt, purchase order, or goods receipt.

## Explicitly not in this release

- SMTP/email notifications
- multiple staff accounts
- multiple branches
- application-managed automated backups
- prescriptions, patient records, insurance, or clinical workflows
