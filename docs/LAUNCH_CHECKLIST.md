# Launch checklist

None of the legal items below have been verified. They are the areas to review with a qualified Ugandan lawyer and accountant before a public launch.

## Legal & regulatory (verify with professionals)
- [ ] **Company registration** with URSB; trading licence for your operating location.
- [ ] **Data protection:** Data Protection and Privacy Act, 2019 and its 2021 Regulations. Register with the Personal Data Protection Office (PDPO, under NITA-U), appoint a data protection officer, finalise the privacy policy, and set data retention periods.
- [ ] **Terms & privacy pages:** replace the drafts at `/terms` and `/privacy`.
- [ ] **Electronic Transactions Act, 2011** and **Computer Misuse Act** (as amended): e-commerce disclosures, record keeping.
- [ ] **Consumer protection:** clear seller/platform responsibilities, honest advertising, sponsored labels (already labelled in the UI).
- [ ] **Payments:** National Payment Systems Act, 2020, if you collect or hold user funds; provider merchant agreements.
- [ ] **Tax:** URA registration; VAT thresholds; how platform fees are invoiced; any digital-services tax obligations.
- [ ] **Universities:** permission to use institution names; campus partnerships.
- [ ] **Minors:** decide a minimum age (most students are 18+) and enforce it at registration.

## Technical
- [ ] Production Postgres with automated daily backups and a tested restore.
- [ ] Object storage adapter (`src/lib/storage.ts`); image resizing to save students' data.
- [ ] Email adapter (`src/lib/email.ts`) with SPF/DKIM on your domain.
- [ ] Shared rate-limit store (Redis/Upstash) if running more than one instance.
- [ ] Error monitoring (e.g. Sentry) and uptime checks.
- [ ] HTTPS everywhere (secure cookies are automatic in production).
- [ ] Run `npm run db:seed -- --reference-only` (never load sample data in production).
- [ ] Create admin accounts with `npm run make-admin` and remove unused staff roles.
- [ ] End-to-end browser tests (Playwright) for register → list → message → mark sold, and for moderation.

## Operations
- [ ] Moderator rota and response targets for reports.
- [ ] Support inbox (support@, privacy@, partners@ addresses used in the UI).
- [ ] Business verification procedure (documents checked, visit/call), recorded in the verification note.
