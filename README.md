# chriswjohnston.ca

Personal campaign website for Chris Johnston — Nipissing Township Council 2026.

## How it works

This repo auto-manages two modes via GitHub Actions:

- **Before launch date** → serves `src/countdown.html` (just a countdown timer)
- **On/after launch date** → serves `src/campaign/index.html` (full campaign site)

The GitHub Actions workflow runs daily at 9 AM Eastern and checks the date automatically. No manual action needed on launch day.

## Setup

### 1. Create the repo and enable GitHub Pages
- Create a new GitHub repo called `chriswjohnston-site` (or any name)
- Upload all files from this folder
- Go to **Settings → Pages → Source → Deploy from branch → `main` → `/docs`**
- Save

### 2. Set your custom domain
- In cPanel DNS, add a CNAME: `@` → `chriswjohnston.github.io`  
  (or if you keep cPanel hosting, just upload `docs/index.html` to `/public_html/`)
- In GitHub Pages settings, enter `chriswjohnston.ca` as custom domain

### 3. Set your launch date
Edit `.github/workflows/build.yml` and change:
```yaml
LAUNCH="2026-10-01"
```
to your actual announcement date in `YYYY-MM-DD` format.

### 4. Set up the contact form
1. Go to [formspree.io](https://formspree.io) and create a free account
2. Create a form — copy the ID (e.g. `xpzgkwqr`)
3. In `src/campaign/index.html`, replace `YOUR_FORM_ID` with your actual ID

### 5. Run the workflow manually once
Actions → Build Site → Run workflow — this builds the initial `docs/` folder.

## File structure

```
chriswjohnston-site/
├── .github/
│   └── workflows/
│       └── build.yml          ← Auto-launch workflow (edit launch date here)
├── src/
│   ├── countdown.html         ← Countdown timer page (pre-announcement)
│   └── campaign/
│       └── index.html         ← Full campaign site (post-announcement)
├── docs/                      ← Built output served by GitHub Pages
│   └── index.html             ← Auto-generated, don't edit directly
└── README.md
```

## Updating the campaign site

Edit `src/campaign/index.html` directly in GitHub and commit. The next daily workflow run will copy it to `docs/`. Or trigger **Run workflow** manually for an immediate update.

## Countdown timer date

The countdown in `src/countdown.html` has its own date setting near the bottom of the file:
```javascript
const LAUNCH = new Date("October 1, 2026 09:00:00 EDT");
```
This controls what the timer counts down to. Keep it in sync with the `LAUNCH` date in `build.yml`.
