# CampusHub architecture

## Principles

1. **One account, many roles.** Anyone can buy, sell, post gigs, apply, and own businesses with a single account. Staff powers (`admin`, `moderator`, `support`) live in `user_roles`, are granted only by an admin or the CLI, and are checked on the server.
2. **Logic in one place.** `src/server/*` functions take `(db, actor, input)`, enforce permissions with `assert*` helpers from `src/lib/permissions.ts`, and are covered by integration tests. Pages and server actions are thin.
3. **Honest data.** Sample content is flagged `is_sample`; test payments `is_test`. Analytics exclude both by default. Payment state is never inferred from the browser.
4. **Money is integer UGX.** Rates are basis points. `computeFee` uses integer arithmetic.
5. **Multi-campus.** Institutions → campuses; users have a primary campus; listings, gigs and deals are campus-scoped. Admins add campuses without code changes.

## Request flow

```
Browser ──form POST──▶ Server Action (src/app/actions)        ← validation (zod), rate limit
                              │
                              ▼
                     Service (src/server)                      ← permission checks, transactions, audit, notifications
                              │
                              ▼
                     Drizzle ORM ──▶ PostgreSQL (PGlite in dev)
```

## Data model (Phase 1, implemented)

| Area | Tables |
| --- | --- |
| Campuses | `institutions`, `campuses`, `user_campuses` |
| Identity | `users`, `user_roles`, `sessions`, `auth_tokens`, `email_outbox` (dev) |
| Marketplace | `categories`, `listings`, `listing_images`, `files`, `favourites` |
| Gigs | `gigs`, `gig_applications`, `reviews` |
| Business | `businesses`, `deals`, `deal_claims`, `promotions` |
| Messaging | `conversations`, `conversation_participants`, `messages`, `notifications` |
| Trust | `reports`, `audit_logs` |
| Money | `platform_settings`, `transactions`, `payments`, `payment_events` |

Key integrity rules enforced by the database:
- One open report per (reporter, target); one review per (reviewer, context); one claim per (user, deal); unique claim codes.
- One transaction per sold listing / completed gig (`transactions_reference_uq`).
- Webhook events unique per (provider, event_id) → idempotent processing.
- Deal claim caps are applied with a conditional `UPDATE … WHERE claim_count < max_claims`.
- Gig assignment uses `UPDATE … WHERE status = 'open'` so two accepts can't both win.

## State machines

**Listing:** `active ⇄ paused → sold`; `removed` by moderators; owner delete is a hard delete unless a transaction exists.

**Gig:** `open → assigned → completed` (both parties confirm); `open|assigned → cancelled` (poster); `assigned → disputed → completed|cancelled` (moderator).

**Deal:** `pending_review → active ⇄ paused`; `rejected`/`removed` by moderators. Verified businesses skip review.

**Transaction vs payment:** a transaction records the agreement (`status`); `payment_status` is separate (`offline_unverified` today); `fee_status` tracks the platform fee (`not_charged → accrued → collected`).

## Roadmap

### Phase 2: transaction infrastructure
- Mobile-money integration (see [PAYMENTS.md](PAYMENTS.md)); escrow-style checkout for marketplace and gigs; fee collection, refunds, payouts.
- Food ordering: `restaurants`, `menu_items`, `orders`, `order_items`, `delivery_zones` (order status separate from payment status).
- Printing: `print_shops`, `print_jobs` with **private** `files` (`is_public=false`), signed URLs and a retention job that deletes documents after N days.
- Accommodation: `properties`, `rooms`, `enquiries`, `viewings`, `bookings` (distinct states; no "reserved" without landlord confirmation).
- Phone OTP verification via an SMS provider (e.g. Africa's Talking).

### Phase 3: ecosystem
- Events: `events`, `ticket_types` (inventory), `tickets` (unique code + QR, `redeemed_at` single-use).
- Tutoring and services bookings: `provider_profiles`, `service_offerings`, `availability_slots`, `bookings`.
- Jobs: `employers`, `jobs`, `job_applications` (never fees to apply).
- Premium: `membership_plans`, `subscriptions`, `entitlements` (benefits only active when a paid subscription exists).
- Rewards: `reward_ledger` (append-only, double-entry style), `referrals`, `discount_codes`.

### Phase 4: growth
- Campus ambassador tools, richer business analytics, recommendations, expansion to graduates/young professionals, additional languages (UI strings are plain English today; wrap with an i18n layer before adding Luganda/Swahili).

## Scaling notes
- Rate limiting is in-memory (single instance). Move to Redis/Upstash when running more than one instance.
- Search uses `ILIKE`. Add a `tsvector` column + GIN index or Postgres `pg_trgm` when listings exceed ~50k.
- Images are served as uploaded. Add resizing (sharp) or an image CDN to save students' data.
