"""
send_digest.py - Sends biweekly digest via Resend + posts to Facebook page
"""
import json, os, re, requests
from datetime import datetime
from pathlib import Path

RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "")
FB_PAGE_TOKEN   = os.environ.get("FB_PAGE_TOKEN", "")
FB_PAGE_ID      = os.environ.get("FB_PAGE_ID", "")
FROM_EMAIL      = "digest@chriswjohnston.ca"
FROM_NAME       = "Nipissing Township Updates"
REPLY_TO        = "chris@chriswjohnston.ca"
SITE_URL        = "https://chriswjohnston.ca"
COUNCIL_URL     = "https://council.chriswjohnston.ca"

NEWS_FILE        = Path("src/news.json")
SUBSCRIBERS_FILE = Path("subscribers.json")
SUMMARIES_FILE   = Path("summaries.json")

def load_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default

def get_latest_summary():
    summaries = load_json(SUMMARIES_FILE, {})
    if not summaries: return None, None
    def parse_key(k):
        slug = k.split("/")[-1]
        slug = re.sub(r"^special-meeting-", "", slug)
        parts = slug.split("-")
        try: return datetime.strptime("-".join(parts[-3:]), "%B-%d-%Y")
        except: return datetime.min
    latest = max(summaries, key=parse_key, default=None)
    if not latest: return None, None
    date_display = latest.split("/")[-1].replace("-", " ").title()
    return date_display, summaries[latest]

def render_md(md):
    if not md: return ""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", md).strip()

def build_html(posts, summary_date, summary_text, email):
    news_rows = ""
    for p in posts[:5]:
        news_rows += f"""
        <tr><td style="padding:12px 0;border-bottom:1px solid #e8d5a3;">
          <a href="{p['url']}" style="font-family:Georgia,serif;font-size:16px;font-weight:bold;color:#2C4A3E;text-decoration:none;">{p['title']}</a>
          <p style="margin:3px 0 0;font-size:12px;color:#999;">{p.get('source','')} &nbsp;·&nbsp; {p.get('date','')}</p>
          {f'<p style="margin:5px 0 0;font-size:13px;color:#555;line-height:1.6;">{p["excerpt"]}</p>' if p.get('excerpt') else ''}
        </td></tr>"""

    summary_section = ""
    if summary_text:
        summary_section = f"""
        <tr><td style="padding:24px 0 0;">
          <h2 style="font-family:Georgia,serif;font-size:20px;color:#2C4A3E;margin:0 0 4px;border-bottom:3px solid #E8C98A;padding-bottom:8px;">Latest Council Meeting Summary</h2>
          <p style="font-size:12px;color:#999;margin:4px 0 16px;">{summary_date} &nbsp;·&nbsp; <a href="{COUNCIL_URL}" style="color:#C06830;">Full archive →</a></p>
          <div style="background:#faf8f3;border-left:4px solid #E8C98A;padding:16px 20px;border-radius:0 8px 8px 0;font-size:14px;color:#444;line-height:1.75;white-space:pre-wrap;">{render_md(summary_text)}</div>
          <p style="font-size:11px;color:#bbb;margin:8px 0 0;">AI-generated from meeting documents. Refer to official minutes for authoritative information.</p>
        </td></tr>"""

    unsubscribe = f"{SITE_URL}/unsubscribe?email={email}"
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f0e8;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f0e8;padding:20px 0;">
<tr><td align="center"><table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr><td style="background:#2C4A3E;padding:28px 32px;border-bottom:4px solid #E8C98A;">
    <p style="margin:0;font-size:11px;color:#E8C98A;letter-spacing:2px;text-transform:uppercase;">Nipissing Township</p>
    <h1 style="margin:4px 0 0;font-family:Georgia,serif;font-size:24px;color:#fff;">Community Update</h1>
    <p style="margin:6px 0 0;font-size:13px;color:rgba(255,255,255,0.6);">{datetime.now().strftime('%B %d, %Y')}</p>
  </td></tr>
  <tr><td style="background:#fff;padding:28px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding-bottom:20px;border-bottom:1px solid #e8d5a3;">
        <p style="margin:0;font-size:15px;color:#444;line-height:1.65;">Here's what's been happening in Nipissing Township.</p>
      </td></tr>
      <tr><td style="padding:20px 0 4px;">
        <h2 style="font-family:Georgia,serif;font-size:20px;color:#2C4A3E;margin:0;border-bottom:3px solid #E8C98A;padding-bottom:8px;">Township News</h2>
      </td></tr>
      {news_rows}
      <tr><td style="padding:16px 0 0;"><a href="{SITE_URL}/news/" style="font-size:13px;color:#C06830;text-decoration:none;">View all news →</a></td></tr>
      {summary_section}
    </table>
  </td></tr>
  <tr><td style="background:#1E2B2A;padding:20px 32px;text-align:center;">
    <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.4);line-height:1.8;">
      You signed up at <a href="{SITE_URL}" style="color:#E8C98A;">{SITE_URL}</a><br>
      <a href="{unsubscribe}" style="color:rgba(255,255,255,0.3);">Unsubscribe</a>
    </p>
  </td></tr>
</table></td></tr></table></body></html>"""

def build_text(posts, summary_date, summary_text):
    lines = [f"NIPISSING TOWNSHIP UPDATE — {datetime.now().strftime('%B %d, %Y')}", "="*40, ""]
    for p in posts[:5]:
        lines += [f"{p['title']}", f"{p.get('source','')} · {p.get('date','')}", p.get('excerpt',''), p['url'], ""]
    if summary_text:
        lines += [f"COUNCIL MEETING SUMMARY — {summary_date}", "-"*30, render_md(summary_text), "", f"Full archive: {COUNCIL_URL}"]
    return "\n".join(lines)

def post_to_facebook(posts, summary_date):
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        print("  No Facebook page credentials — skipping")
        return
    items = "\n".join([f"• {p['title']} ({p.get('source','')})" for p in posts[:5]])
    summary_line = f"\n\n📋 Latest Council Meeting: {summary_date}\n{COUNCIL_URL}" if summary_date else ""
    message = f"🗞️ Nipissing Township Update — {datetime.now().strftime('%B %d, %Y')}\n\n{items}{summary_line}\n\nFull digest + council archive: {SITE_URL}"
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed",
            data={"message": message, "access_token": FB_PAGE_TOKEN},
            timeout=15
        )
        if resp.status_code == 200:
            print(f"  ✓ Posted to Facebook page")
        else:
            print(f"  ✗ Facebook post failed: {resp.text[:100]}")
    except Exception as e:
        print(f"  ✗ Facebook error: {e}")

if __name__ == "__main__":
    print("="*50)
    print(f"Digest Sender — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)

    if not RESEND_API_KEY:
        print("ERROR: RESEND_API_KEY not set"); exit(1)

    news_data   = load_json(NEWS_FILE, {"posts": []})
    posts       = news_data.get("posts", [])[:5]
    subscribers = load_json(SUBSCRIBERS_FILE, {"subscribers": []}).get("subscribers", [])
    summary_date, summary_text = get_latest_summary()

    if not posts: print("No posts — exiting"); exit(0)

    subject = f"Nipissing Township Update — {datetime.now().strftime('%B %d, %Y')}"
    plain   = build_text(posts, summary_date, summary_text)

    print(f"\nSending to {len(subscribers)} subscriber(s)...")
    sent = failed = 0
    for sub in subscribers:
        email = sub if isinstance(sub, str) else sub.get("email", "")
        if not email: continue
        html = build_html(posts, summary_date, summary_text, email)
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": f"{FROM_NAME} <{FROM_EMAIL}>", "to": [email],
                      "reply_to": REPLY_TO, "subject": subject, "html": html, "text": plain},
                timeout=30
            )
            if resp.status_code == 200:
                sent += 1; print(f"  ✓ {email}")
            else:
                failed += 1; print(f"  ✗ {email}: {resp.text[:80]}")
        except Exception as e:
            failed += 1; print(f"  ✗ {email}: {e}")

    print(f"\n✓ Email: {sent} sent, {failed} failed")

    print("\nPosting to Facebook...")
    post_to_facebook(posts, summary_date)
    print("\n✓ All done.")
