# Payments integration (Phase 2)

## What exists today
- `src/lib/payments/types.ts`: the `PaymentProvider` interface (`initiate`, `verifyWebhook`, `parseWebhook`).
- `src/lib/payments/test-provider.ts`: a test provider that never moves money. Everything it touches is `is_test = true`.
- `POST /api/payments/webhook/[provider]`: verifies the signature, stores the raw event in `payment_events` (unique per provider + event id, so duplicates are ignored), checks the amount matches, and moves a payment from `pending` to its final state exactly once. Covered by tests.
- Commission rates per module in **Admin → Fees & settings** (stored in basis points, audited). Commissions are **off** by default.

## What's needed to go live
1. **Choose a provider.** Options for Uganda include direct MTN MoMo and Airtel Money APIs, or an aggregator (e.g. Flutterwave, Pesapal, DPO) that covers both plus cards. An aggregator is usually faster to launch with.
2. **Commercial and regulatory approval.** The provider will require business registration (URSB), KYC, and possibly a merchant agreement. If CampusHub holds funds on behalf of users (escrow), check whether a Bank of Uganda licence or a licensed partner is required under the National Payment Systems Act, 2020.
3. **Implement the adapter** in `src/lib/payments/<provider>.ts` using the provider's official docs: request-to-pay/collection, webhook signature verification (constant-time compare), and a status-query function for reconciliation.
4. **Add a reconciliation job** that queries the provider for `pending` payments older than N minutes and settles them, and a daily report comparing provider settlements with `payments`.
5. **Checkout flows.** Create a `payment` row (`pending`) → call `initiate` → show "Approve the prompt on your phone" → wait for the webhook. Only then mark the order/transaction paid and set `fee_status = 'collected'`.
6. **Refunds and payouts** need their own tables (`refunds`, `payouts`) linked to `payments`, so commissions, refunds and payouts stay separately traceable.

Never mark something paid from a browser redirect, never store card numbers, and keep all secrets in server-side environment variables.
