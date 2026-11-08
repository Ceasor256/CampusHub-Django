# CampusHub (Django)

CampusHub is a campus marketplace for Uganda. Students buy and sell, post and complete small jobs ("gigs"), and claim discounts from businesses near their university. It supports many universities and campuses from the start, and all prices are in Uganda Shillings (UGX).

This folder is the **Django version** of CampusHub. It stands on its own and doesn't need the Next.js version.

**Status: Phase 1 (first working version).** Marketplace, gigs, business deals, messaging, notifications, reporting, moderation and the staff dashboard all work and save to the database. **Payments are not live yet**: buyers and sellers pay each other directly, outside the app.

---

## Contents

1. [Quick start](#1-quick-start)
2. [The virtual environment (`venv`)](#2-the-virtual-environment-venv)
3. [Logging in: test accounts](#3-logging-in-test-accounts)
4. [Using CampusHub as a student](#4-using-campushub-as-a-student)
5. [Using CampusHub as a business](#5-using-campushub-as-a-business)
6. [Using the staff dashboard](#6-using-the-staff-dashboard)
7. [The 3D tour (scroll story)](#7-the-3d-tour-scroll-story)
8. [Sample data and resetting the database](#8-sample-data-and-resetting-the-database)
9. [Running the tests](#9-running-the-tests)
10. [Changing the design](#10-changing-the-design)
11. [Settings and configuration](#11-settings-and-configuration)
12. [Putting it online (deployment)](#12-putting-it-online-deployment)
13. [Troubleshooting](#13-troubleshooting)
14. [What's not built yet](#14-whats-not-built-yet)
15. [How the code is organised](#15-how-the-code-is-organised)

---

## 1. Quick start

You need **Python 3.12 or newer** installed (this machine has Python 3.14).

1. **Set up once:** double-click **`setup.bat`**. It creates the virtual environment, installs the packages, creates the database and loads sample data. It takes a minute or two.
2. **Start the app:** double-click **`run.bat`**. Leave that window open while you use the app.
3. **Open it:** go to **http://localhost:8010** in your browser.

To stop the app, click the `run.bat` window and press **Ctrl+C**, or just close the window.

You can run `setup.bat` again at any time. It won't delete anything.

---

## 2. The virtual environment (`venv`)

A virtual environment is a private copy of Python with this project's packages installed, so it doesn't mix with other projects on your computer.

| | |
| --- | --- |
| **Name** | `venv` |
| **Where** | the `venv` folder inside `CampusHub-Django` |
| **Python** | `venv\Scripts\python.exe` |
| **Packages** | Django 6.1.2, Pillow, WhiteNoise, dj-database-url (listed in `requirements.txt`) |

There is **only one** environment for this project. Always use it, not the Python installed on your computer, or you'll see errors like "No module named django".

### Using it in VS Code

1. **File → Open Folder** and choose the **`CampusHub-Django`** folder itself (not its parent folder).
2. VS Code picks up `venv` automatically: `.vscode/settings.json` tells it to. If you see a different Python in the bottom-right corner, click it and choose `.\venv\Scripts\python.exe`.
3. Press **F5** and choose **"CampusHub: run server (port 8010)"** to start the app, or **"CampusHub: run tests"** to run the tests.

### Using it in a terminal

From the `CampusHub-Django` folder:

```powershell
.\venv\Scripts\Activate.ps1
```

Your prompt now starts with `(venv)`, and `python` means the project's Python. Then:

```powershell
python manage.py runserver 8010
```

If PowerShell says running scripts is disabled, skip activation and call the venv's Python directly. This always works:

```powershell
.\venv\Scripts\python.exe manage.py runserver 8010
```

### If the venv is missing or broken

This happens if you move or copy the project folder, because a venv remembers the folder it was created in. Delete the `venv` folder, then double-click `setup.bat`.

---

## 3. Logging in: test accounts

`setup.bat` creates three test accounts **for local development only**:

| Role | Email | Can do |
| --- | --- | --- |
| Admin | `admin@campushub.test` | Everything, including fees, campuses, categories, staff roles and the audit log |
| Moderator | `moderator@campushub.test` | Handle reports, suspend users, verify businesses, approve deals |
| Student | `student@campushub.test` | A normal user account |

The passwords are in **`core/seed.py`**, in the `DEV_ACCOUNTS` list near the top of the file.

It also creates fictional sample sellers, listings, gigs, businesses and deals. These are marked with a yellow **"Sample"** badge, so you can always tell them apart from real content. Nobody can log in as the sample sellers.

You can also register your own account at **/register/**.

---

## 4. Using CampusHub as a student

### Creating an account

1. Click **Join free** (or go to **/register/**). Enter your name, email, an optional Ugandan phone number (`0772 123 456` or `+256 772 123 456`) and a password of at least 8 characters.
2. Choose your **campus**. CampusHub shows listings, gigs and deals from your campus first.
3. **Confirm your email** to get the "Email" trust badge. In development no real emails are sent: open **http://localhost:8010/dev/outbox/** to see the email and click the link. If you need another one, use **Resend confirmation email** on your account page.

**Forgot your password?** Use **Forgot password?** on the login page. The reset link also appears in **/dev/outbox/** during development. It works once and expires after 1 hour.

### Browsing and switching campus

- The **homepage** shows fresh listings, open gigs and deals. Use the **"Showing results for"** box to switch campus, or pick **All campuses**.
- The search bar at the top searches the marketplace.
- On phones, use the bottom tabs: **Home, Market, Gigs, Deals, Me**.

### Marketplace: buying

1. Go to **Marketplace**. Filter by category, keyword, campus, condition and price, and sort by newest or price.
2. Open a listing to see photos, the description, the meet-up spot and the seller's profile (rating, badges, member since).
3. Click **Save** to keep it in **Me → Saved**.
4. Write to the seller in the message box (tap a suggestion like "Is this still available?") and click **Send message**. Your phone number stays private.
5. Meet in a busy public place on campus, check the item, then pay. See **/safety/** for tips.

### Marketplace: selling

1. Click **Post → Sell an item** (or **/marketplace/new/**).
2. Add up to **6 photos** (JPG, PNG or WebP, up to 6 MB each). Photos are resized automatically and their location data is removed for your privacy.
3. Fill in the title, category, condition, description, price in UGX (`450000` or `450,000`; use `0` to give it away), campus and a meet-up spot.
4. Click **Publish listing**. It's live straight away.

On your listing page you can:
- **Edit** it: change details, remove photos or add new ones.
- **Pause** it to hide it from search, then **Resume** later.
- **Mark as sold**: choose the buyer (only people who messaged you are listed) and the final price. This records the sale, and the buyer sees it under **Me → Purchases**.
- **Delete** it. Sold listings are hidden instead of erased, so the sale record survives.

### Gigs (small jobs)

**To get something done:**
1. **Post → Post a gig** (or **/gigs/new/**). Describe the task, budget (at least UGX 1,000), deadline, in person or remote, and campus.
2. Students apply with a message and their price. Open your gig to see the **Applicants** and click **Choose** on the one you want. Everyone else is told the gig was filled.
3. Use the message box to agree on details.
4. When the work is done, both of you click confirm. The gig is then **Completed** and you can leave each other a 1–5 star review.
5. You can **Cancel** an open gig, or an assigned one if the worker hasn't marked it done yet. If something goes wrong, click **Open a dispute** and a moderator will review it.

**To earn:** browse **Gigs**, open one and click **Send application**. You can **Withdraw** while it's pending. If you're chosen, you get a notification. Click **I've finished the work** when you're done.

> Gigs that ask someone to sit an exam or complete graded coursework for someone else are blocked. Tutoring and study help are welcome.

### Deals

1. Go to **Deals** to see discounts from businesses near campus.
2. Open a deal and click **Claim this deal**. You get a unique code like `CH-7KQ2MZ9P`.
3. Show the code at the business counter. Each code works **once**, and you can claim each deal only once.
4. Find all your codes under **Me → My deals**.

Some deals are only for one campus, and some have a limited number of claims.

### Messages and notifications

- **Messages** (speech-bubble icon) lists all your chats. Press **Enter** to send and **Shift+Enter** for a new line.
- **Notifications** (bell icon) tells you about applications, chosen gigs, sales, deal updates and moderation decisions.

### Your account (Me)

The **Me** page has your profile card, verification badges, and tabs for **My listings, My gigs, Saved, My deals** and **Purchases**.

**Settings** lets you change your name, campus, phone and bio, and **delete your account**. Deleting removes your personal details, takes down your listings and cancels your open gigs. It needs your password and the word `DELETE`.

### Reporting a problem

Every listing, gig, deal, business and profile has a **Report** button. Choose a reason (scam, prohibited item, harassment and so on) and add details. Reports are confidential, and moderators review each one.

---

## 5. Using CampusHub as a business

Any account can create up to 3 business profiles.

1. Go to **/business/** (footer link **List your business**), fill in the business name, type, description, address and phone, and click **Create business profile**.
2. **Request verification** on your business dashboard. Explain how CampusHub can check you, for example your URSB registration number. A moderator then approves or rejects the request.
3. Click **New deal** and fill in the headline ("20% off"), description, prices, terms, campus (or all campuses), end date, how students redeem it (unique code per student is recommended) and an optional claim limit.
   - **Verified** businesses: the deal goes live immediately.
   - **Unverified** businesses: the deal waits for a moderator to approve it.
4. **At the counter**, type the student's code into **Redeem a student code**. Each code can only be redeemed once; a second attempt shows when it was first used.
5. The dashboard shows views, claims and redemptions for each deal. You can **Pause** or **Resume** a deal, and edit your business profile at the bottom.

Your public business page is at `/b/<your-business-name>/`.

---

## 6. Using the staff dashboard

Log in as the admin or moderator account and click **Staff** in the top bar (or go to **/staff/**).

| Page | What you do there | Who |
| --- | --- | --- |
| **Overview** | Users, active users, listings, gigs, deal claims, open reports, GMV and revenue for the last 7, 30 or 90 days, plus a 14-day chart. Sample data is hidden unless you click "Include sample data". | All staff |
| **Reports & disputes** | Review reports: **Dismiss**, **Remove** the content, or **Remove + suspend** the owner. Resolve gig disputes as completed or cancelled. | Moderators, admins |
| **Users** | Search users; verify students; **Suspend** (signs them out everywhere) or **Restore**; give or remove the moderator or admin role. | Moderators; admins for roles |
| **Businesses** | Approve or reject verification requests; suspend or restore businesses. | Moderators, admins |
| **Deals** | Approve or reject deals waiting for review; remove deals. | Moderators, admins |
| **Transactions** | Every recorded sale and completed gig: amount, platform fee and payment status. | All staff |
| **Campuses** | Add universities and campuses; switch campuses on or off. | Admins |
| **Categories** | Add marketplace or gig categories; switch them on or off. | Admins |
| **Fees & settings** | Commission rates (marketplace 5%, gigs 10% by default) and the switch that turns commission charging on. Leave it off until payments are live. | Admins |
| **Audit log** | A permanent record of every staff action and settings change. | Admins |

**Support** staff can view everything but can't take actions.

Moderators can also remove a listing or gig directly from its page, using the red **Moderator: remove** button.

### Making someone an admin

Once someone has registered, either:

- log in as an admin and click **+ admin** next to their name on **Users**, or
- run this in a terminal:

```powershell
.\venv\Scripts\python.exe manage.py make_admin their@email.com
```

### The Django admin

**/django-admin/** is Django's built-in database browser, for technical work only. To get access, create a superuser:

```powershell
.\venv\Scripts\python.exe manage.py createsuperuser
```

---

## 7. The 3D tour (scroll story)

CampusHub has an animated 3D story that explains the platform as you scroll. It appears in two places:

- **On the homepage**, in the dark section below the deals ("How CampusHub works"). The **"See how CampusHub works →"** link in the top banner jumps straight to it.
- **On its own page** at **http://localhost:8010/tour/**. It's also linked in the footer as **"How it works (3D tour)"**.

### What happens as you scroll

The CampusHub logo appears as a 3D object: the four white dots fly in and snap into place. Each screen of scrolling turns it half a turn and plays one chapter:

| Chapter | On screen | Button |
| --- | --- | --- |
| 1. The hub | The logo assembles | (scroll hint) |
| 2. Buy & sell | A phone, laptop and textbook orbit the hub | Browse the marketplace |
| 3. Gigs | Task cards fan out in front of the hub | Find a gig |
| 4. Deals | Golden discount tickets fall and spin; the core glows | See today's deals |
| 5. Join | The hub faces you and a ring pulses outward | Join free / Start selling (or "Post something" if you're logged in) |

Moving the mouse tilts the view slightly.

### It never slows down the rest of the site

- The 3D code (`static/js/story-scene.js`, about 150 KB compressed) is **only downloaded when you scroll close to the story**. Other pages never load it.
- It only animates while the story is on screen, and pauses when you switch tabs.
- On weaker phones it automatically draws fewer particles and at a lower resolution.
- Everyone gets the same content. If a visitor has **reduce motion** turned on, has **data saver** on, uses a device or browser **without 3D (WebGL) support**, or has JavaScript off, the story shows as five simple cards instead.

### Changing the text

Edit **`templates/includes/story.html`**. Each chapter is one `<article class="story-chapter">` block with an eyebrow, a title, a paragraph and a button. Save and refresh the browser; no rebuild needed.

Keep **exactly five chapters**: the 3D animation has one scene per chapter.

### Changing the 3D animation

The scene's source code is **`assets/story/scene.js`**: the objects, colours, lighting, camera path and what happens in each chapter. After changing it, rebuild the bundle (this needs Node.js):

```powershell
npm install
```

```powershell
npm run story
```

This writes `static/js/story-scene.js`. Refresh the browser (use **Ctrl+F5** if you still see the old version). To rebuild both the CSS and the 3D scene in one go, use `npm run build`.

The story's layout and fallback-card styles are at the end of **`assets/app.css`** (search for "3D scroll story"). Rebuild them with `npm run css`.

### Removing it

- **From the homepage only:** in `templates/core/home.html`, delete the line `{% include "includes/story.html" %}`. Also delete the "See how CampusHub works" link in the top banner, because it points to the story. The `/tour/` page keeps working.
- **Completely:** also delete the `tour/` line in `config/urls.py`, the footer link in `templates/base.html`, and the files `templates/core/tour.html`, `templates/includes/story.html`, `static/js/story.js`, `static/js/story-scene.js` and `assets/story/`.

---

## 8. Sample data and resetting the database

The database is a single file, **`db.sqlite3`**, in the project folder.

**To start fresh:** stop the app, delete `db.sqlite3`, then double-click `setup.bat`. You get a new database with the 7 universities, the categories, the test accounts and the sample content.

Universities and campuses loaded by default: Makerere (Main), MUBS (Nakawa), Kyambogo, UCU (Mukono), KIU (Kansanga), MUST (Mbarara) and Gulu.

**For a real launch**, load only the universities and categories, with no sample content:

```powershell
.\venv\Scripts\python.exe manage.py seed --reference-only
```

---

## 9. Running the tests

```powershell
.\venv\Scripts\python.exe manage.py test tests
```

You should see `Ran 23 tests ... OK`. They cover money and phone formatting, the marketplace, gigs, deals, messaging, moderation, permissions, image uploads, the payment webhook and the 3D tour pages. You can also press **F5** in VS Code and choose **"CampusHub: run tests"**.

---

## 10. Changing the design

The pages are HTML templates in **`templates/`**. The colours and fonts are in **`assets/app.css`**, which is compiled into `static/css/app.css`.

After changing class names in templates or editing `assets/app.css`, rebuild the CSS. This needs Node.js:

```powershell
npm install
```

```powershell
npm run css
```

Text-only changes in templates don't need a rebuild; just refresh the browser.

### The current look: "Café" theme

The site uses a warm coffee-shop style:

| Part | What it uses | Where to change it |
|---|---|---|
| Main colour (buttons, links) | Espresso brown `#7b5233` (`brand-600`) | `--color-brand-*` in the `@theme` block of `assets/app.css` |
| Dark sections (hero, 3D tour) | Dark roast `#22150d` (`brand-950`) | same place |
| Accent (highlights, gig card) | Soft gold `#d9ae63` (`accent-400`) | `--color-accent-*` |
| Page background and cards | Cream `#f7f1e8` and `#fffdf9` | `--color-canvas`, `--color-surface` |
| Text | Warm dark brown `#2a1e17` | `--color-ink`, `--color-ink-2`, `--color-ink-3` |
| Headings (`h1`, `h2`, the logo name) | **Playfair Display** (serif) | `--font-display` |
| Body text | **Plus Jakarta Sans** | `--font-sans` |
| Buttons | Rounded "pill" shape | `.btn` in `assets/app.css` |

Both fonts are stored inside the project in `static/font/`, so the site makes no requests to Google Fonts.

A few colours live outside `app.css`, so change these too if you pick a new palette:

- `templates/includes/logo.html` and `static/img/icon.svg`: the logo
- `templates/base.html`: `<meta name="theme-color">`, the colour of the phone's address bar
- `templates/staff/overview.html`: the chart bars
- `assets/story/scene.js`: the `COLOR` list for the 3D tour (rebuild it with `npm run story`)

After changing colours, rebuild everything with one command:

```powershell
npm run build
```

**Going back to the old purple look:** the earlier theme was saved to `CampusHub-Django-purple-theme-backup.zip` on your Desktop. Unzip it and copy its files over the project, replacing the current ones. This also brings back the older README, which doesn't have this section. Then run `npm run build` and restart the server.

---

## 11. Settings and configuration

For local use you don't need to change anything.

To change settings, copy **`.env.example`** to **`.env`** and edit it. It's read automatically.

| Setting | What it does |
| --- | --- |
| `DJANGO_DEBUG` | `true` for development; must be `false` online |
| `DJANGO_SECRET_KEY` | Required when debug is off; keep it secret |
| `DJANGO_ALLOWED_HOSTS` | Your domain name(s) |
| `DATABASE_URL` | Empty = `db.sqlite3`. Online, use a PostgreSQL address |
| `APP_URL` | The public address, used in email links |
| `EMAIL_*` | Real email sending, instead of `/dev/outbox/` |
| `REDIS_URL` | Shared limits when running several servers |
| `PAYMENT_PROVIDER`, `PAYMENT_WEBHOOK_SECRET` | For the future payments integration |

---

## 12. Putting it online (deployment)

1. Create a PostgreSQL database (Supabase, Neon, Railway or Render) and set `DATABASE_URL`.
2. Set `DJANGO_DEBUG=false`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain` and `APP_URL`.
3. Install the production packages: `pip install -r requirements-prod.txt`
4. Run `python manage.py migrate`, then `python manage.py seed --reference-only`, then `python manage.py collectstatic --noinput`.
5. Start it with `gunicorn config.wsgi --workers 3` behind HTTPS.
6. **Photos:** use cloud storage (Supabase Storage, Cloudflare R2 or S3, via `django-storages`) so uploads survive redeploys.
7. **Email:** set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and your email provider's SMTP settings.
8. Before going public, work through **`docs/LAUNCH_CHECKLIST.md`** (data protection, tax, payments and terms).

---

## 13. Troubleshooting

| Problem | Fix |
| --- | --- |
| **"No module named django"** (or Pillow, WhiteNoise) | You're using your computer's Python instead of `venv`. In VS Code, open the `CampusHub-Django` folder and select `.\venv\Scripts\python.exe` (bottom-right corner). In a terminal, use `.\venv\Scripts\python.exe` instead of `python`. |
| **"running scripts is disabled"** when activating | Skip activation and use `.\venv\Scripts\python.exe manage.py ...` directly. |
| **"That port is already in use"** | Another program is using 8010. Close the other `run.bat` window, or use another port: `.\venv\Scripts\python.exe manage.py runserver 8020` |
| **venv stopped working after moving the folder** | Delete the `venv` folder and run `setup.bat`. |
| **"no such table"** or other database errors | Run `.\venv\Scripts\python.exe manage.py migrate`. If it still fails, reset the database (section 8). |
| **I didn't get the confirmation or reset email** | In development, emails appear at http://localhost:8010/dev/outbox/. |
| **The 3D tour shows plain cards instead of the animation** | That's the built-in fallback. It appears when reduce motion or data saver is on, or when the browser or device has no 3D (WebGL) support. Try another browser, or check that hardware acceleration is turned on. |
| **I changed `assets/story/scene.js` but nothing changed** | Run `npm run story`, then refresh with **Ctrl+F5**. |
| **The page looks unstyled** | Make sure `static/css/app.css` exists. If you changed templates, run `npm run css` (section 10). |
| **"Too many attempts"** | Login, signup and some other actions are rate-limited. Wait 10–15 minutes, or restart the app to clear the limits in development. |
| **I can't see the Staff link** | Log in with an account that has the moderator or admin role (section 3). |

---

## 14. What's not built yet

- **Payments:** no money moves through CampusHub yet. Sales are recorded as "paid offline (unverified)". `docs/PAYMENTS.md` explains how to add mobile money (MTN MoMo or Airtel Money) later.
- **Real email sending:** it needs an email provider (see section 11).
- **Later modules:** food delivery, printing, hostels, events, tutoring, student jobs, premium membership and rewards are shown as "coming soon" on **/services/**. The plan is in `docs/ARCHITECTURE.md`.
- **Legal:** the Terms and Privacy pages are drafts and need a Ugandan lawyer's review before launch.

---

## 15. How the code is organised

```
config/        settings and URL routes
core/          campuses, categories, reports, reviews, notifications, audit log,
               helpers (money, phone numbers, permissions, rate limiting), image processing, icons, sample data
accounts/      user accounts: sign up, login, email confirmation, password reset, profile, delete account
marketplace/   listings, photos, saved items, mark as sold
gigs/          gigs, applications, completion, disputes, reviews
deals/         businesses, verification requests, deals, claims, redemption
messaging/     conversations and messages
payments/      transaction records and the payments boundary (test mode only)
staff/         staff dashboard, moderation and analytics
templates/     all the HTML pages (shared pieces are in templates/includes)
assets/        sources for the CSS (app.css) and the 3D scroll story (story/scene.js)
static/        compiled CSS, JavaScript (incl. the built 3D story), font and icon
docs/          architecture, payments plan and launch checklist
tests/         automated tests
setup.bat      one-time setup         run.bat   start the app
```

Every rule and permission check lives in each app's `services.py`, so hiding a button is never the only protection.
