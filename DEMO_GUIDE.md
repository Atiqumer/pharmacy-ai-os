# RxOS Demo Guide

Use this checklist for the public LinkedIn demonstration. Keep the production admin account private and never show environment variables, browser password managers, access tokens, Supabase credentials, or the Groq key on screen.

## Before recording

1. Confirm the frontend and API health pages are online.
2. Use a dedicated demo account, not the admin account.
3. Complete pharmacy setup with a fictional pharmacy name and a 30-day expiry warning.
4. Import [`demo/demo-inventory.csv`](demo/demo-inventory.csv).
5. Create a fictional supplier named `Demo Medical Wholesale`.
6. Close unrelated tabs and hide bookmarks, notifications, and developer tools.
7. Rehearse the full workflow once. Reset quantities by importing the CSV again if needed.

The CSV intentionally produces useful dashboard states: Paracetamol is low and expiring soon, Omeprazole is low, and the remaining products are healthy. Prices and products are demonstration data only.

## 3–5 minute LinkedIn demo story

### 1. The problem — 20 seconds

“Small pharmacy owners often discover low stock or expiring medicine too late because inventory, purchasing, and sales are disconnected. RxOS keeps those operations in one auditable workspace.”

### 2. Setup and import — 35 seconds

- Show the pharmacy setup fields and alert-window setting.
- Import the demo CSV.
- Point out the immediate stock and expiry notification badge.

### 3. Inventory intelligence — 45 seconds

- Show stock value, low-stock and expiry KPIs.
- Filter the inventory to low-stock items.
- Open stock history to show audited quantity changes.
- Ask the inventory assistant: `Which products are low in stock and what should I reorder first?`

### 4. Purchase and receive — 60 seconds

- Open Purchasing and create a purchase order for Paracetamol.
- Submit it, receive it into a new batch, and return to the dashboard.
- Show that the quantity, movement history, and notification badge update.

### 5. Sale and return — 60 seconds

- Complete a small sale containing one or two products.
- Explain FEFO: the earliest-expiring available batch is selected first.
- Open the sale and return one unit.
- Show the exact batch restoration in stock history.

### 6. Owner summary — 30 seconds

- Show the 30-day sales and estimated gross-profit summary.
- Download one CSV report and show the success message.
- Generate the AI morning briefing and point out its exact expiry timing.

### 7. Close — 15 seconds

“This release is focused on one independent pharmacy owner. The next improvements will be driven by real pharmacy use, especially Aronium import compatibility, barcode workflow, and printable documents.”

## Pass/fail checklist

- [ ] Login completes without an unexpected error.
- [ ] Dashboard inventory appears and notifications match its data.
- [ ] Purchase receipt changes stock and clears the relevant low-stock alert.
- [ ] Sale reduces the correct earliest-expiry batch.
- [ ] Return restores the exact original batch.
- [ ] Times display correctly in Pakistan local time.
- [ ] Inventory and sales reports download once with visible feedback.
- [ ] AI briefing uses the configured expiry window and exact days.
- [ ] No real customer data or secrets appear in the recording.

