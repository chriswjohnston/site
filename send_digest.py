"""
Biweekly Digest Sender
=======================
Reads subscribers.json, news.json, and summaries.json
Sends a digest email via Resend API.
Run every other Tuesday via GitHub Actions (same schedule as council scraper).
"""

import json
import os
import re
import requests
from datetime import datetime
from pathlib import Path

RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL      = "digest@chriswjohnston.ca"   # must be verified in Resend
FROM_NAME       = "Nipissing Township Updates"
REPLY_TO        = "chris@chriswjohnston.ca"
COUNCIL_ARCHIVE = "https://council.chriswjohnston.ca"
SITE_URL        = "https://chriswjohnston.ca"

NEWS_FILE        = Path("src/news.json")
SUBSCRIBERS_FILE = Path("subscribers.json")
SUMMARIES_FILE   = Path("summaries.json")   # from council-meetings repo — copy here or symlink


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return default


def get_latest_summary():
    """Get the most recent AI summary from summaries.json."""
    summaries = load_json(SUMMARIES_FILE, {})
    if not summaries:
        return None, None

    # Keys are like "2026/march-17-2026" — find the most recent
    def parse_slug_date(key):
        slug = key.split("/")[-1]
        slug = re.sub(r"^special-meeting-", "", slug)
        parts = slug.rsplit("-", 2)
        if len(parts) == 3:
            try:
                return datetime.strptime(f"{parts[0]}-{parts[1]}-{parts[2]}", "%B-%d-%Y")
            except:
                pass
        return datetime.min

    latest_key = max(summaries.keys(), key=parse_slug_date, default=None)
    if not latest_key:
        return None, None

    # Format the key back to a readable date
    slug = latest_key.split("/")[-1]
    date_display = slug.replace("-", " ").title()
    return date_display, summaries[latest_key]


def render_summary_text(md):
    """Convert markdown summary to plain text."""
    if not md:
        return ""
    md = re.sub(r"\*\*(.+?)\*\*", r"\1", md)
    return md.strip()


def build_email_html(posts, summary_date, summary_text, subscriber_email):
    """Build the HTML email."""

    # News items HTML
    news_html = ""
    for post in posts[:5]:
        news_html += f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #e8d5a3;">
            <a href="{post['url']}" style="font-family:'Georgia',serif;font-size:16px;font-weight:bold;color:#2C4A3E;text-decoration:none;">{post['title']}</a>
            <p style="margin:4px 0 0;font-size:13px;color:#888;">{post.get('date','')}</p>
            {f'<p style="margin:6px 0 0;font-size:14px;color:#555;line-height:1.6;">{post["excerpt"]}</p>' if post.get('excerpt') else ''}
          </td>
        </tr>"""

    # Summary section
    summary_section = ""
    if summary_text:
        summary_section = f"""
        <tr>
          <td style="padding:24px 0 0;">
            <h2 style="font-family:'Georgia',serif;font-size:20px;color:#2C4A3E;margin:0 0 4px;border-bottom:3px solid #E8C98A;padding-bottom:8px;">
              Latest Council Meeting Summary
            </h2>
            <p style="font-size:12px;color:#999;margin:4px 0 16px;">{summary_date} &nbsp;·&nbsp; <a href="{COUNCIL_ARCHIVE}" style="color:#C06830;">View full archive →</a></p>
            <div style="background:#faf8f3;border-left:4px solid #E8C98A;padding:16px 20px;border-radius:0 8px 8px 0;">
              <pre style="font-family:Georgia,serif;font-size:14px;color:#444;line-height:1.75;white-space:pre-wrap;margin:0;">{render_summary_text(summary_text)}</pre>
            </div>
            <p style="font-size:11px;color:#bbb;margin:8px 0 0;">AI-generated summary from meeting documents. Always refer to official minutes.</p>
          </td>
        </tr>"""

    unsubscribe_url = f"{SITE_URL}/unsubscribe?email={subscriber_email}"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f5f0e8;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f0e8;padding:20px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

        <!-- Header -->
        <tr>
          <td style="background:#2C4A3E;padding:28px 32px;border-bottom:4px solid #E8C98A;">
            <p style="margin:0;font-size:11px;color:#E8C98A;letter-spacing:2px;text-transform:uppercase;">Nipissing Township</p>
            <h1 style="margin:4px 0 0;font-family:Georgia,serif;font-size:24px;color:#ffffff;font-weight:bold;">Community Update</h1>
            <p style="margin:6px 0 0;font-size:13px;color:rgba(255,255,255,0.6);">{datetime.now().strftime('%B %d, %Y')}</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="background:#ffffff;padding:28px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0">

              <!-- Intro -->
              <tr>
                <td style="padding-bottom:20px;border-bottom:1px solid #e8d5a3;">
                  <p style="margin:0;font-size:15px;color:#444;line-height:1.65;">
                    Here's what's been happening in Nipissing Township over the past two weeks.
                  </p>
                </td>
              </tr>

              <!-- News heading -->
              <tr>
                <td style="padding:20px 0 4px;">
                  <h2 style="font-family:Georgia,serif;font-size:20px;color:#2C4A3E;margin:0;border-bottom:3px solid #E8C98A;padding-bottom:8px;">
                    Township News
                  </h2>
                </td>
              </tr>

              <!-- News items -->
              {news_html}

              <!-- More link -->
              <tr>
                <td style="padding:16px 0 0;">
                  <a href="{SITE_URL}/news/" style="font-size:13px;color:#C06830;text-decoration:none;">View all township news →</a>
                </td>
              </tr>

              <!-- Summary -->
              {summary_section}

            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#1E2B2A;padding:20px 32px;text-align:center;">
            <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.4);line-height:1.8;">
              You're receiving this because you signed up at <a href="{SITE_URL}" style="color:#E8C98A;">{SITE_URL}</a><br>
              <a href="{unsubscribe_url}" style="color:rgba(255,255,255,0.3);">Unsubscribe</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_email_text(posts, summary_date, summary_text):
    """Plain text fallback."""
    lines = [
        f"NIPISSING TOWNSHIP COMMUNITY UPDATE",
        f"{datetime.now().strftime('%B %d, %Y')}",
        "=" * 40,
        "",
        "TOWNSHIP NEWS",
        "-" * 20,
    ]
    for post in posts[:5]:
        lines.append(f"\n{post['title']}")
        if post.get("date"):
            lines.append(post["date"])
        if post.get("excerpt"):
            lines.append(post["excerpt"])
        lines.append(post["url"])

    if summary_text:
        lines += [
            "",
            f"LATEST COUNCIL MEETING SUMMARY — {summary_date}",
            "-" * 20,
            render_summary_text(summary_text),
            "",
            f"Full archive: {COUNCIL_ARCHIVE}",
        ]

    return "\n".join(lines)


def send_email(to_email, subject, html, text):
    """Send via Resend API."""
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from":     f"{FROM_NAME} <{FROM_EMAIL}>",
            "to":       [to_email],
            "reply_to": REPLY_TO,
            "subject":  subject,
            "html":     html,
            "text":     text,
        },
        timeout=30,
    )
    return resp.status_code == 200, resp.text


if __name__ == "__main__":
    print("=" * 50)
    print("Nipissing Digest Sender")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    if not RESEND_API_KEY:
        print("ERROR: RESEND_API_KEY not set")
        exit(1)

    # Load data
    news_data = load_json(NEWS_FILE, {"posts": []})
    posts = news_data.get("posts", [])[:5]

    subscribers_data = load_json(SUBSCRIBERS_FILE, {"subscribers": []})
    subscribers = subscribers_data.get("subscribers", [])

    summary_date, summary_text = get_latest_summary()

    if not subscribers:
        print("No subscribers — nothing to send.")
        exit(0)

    if not posts:
        print("No news posts — nothing to send.")
        exit(0)

    subject = f"Nipissing Township Update — {datetime.now().strftime('%B %d, %Y')}"
    text = build_email_text(posts, summary_date, summary_text)

    print(f"\nSending to {len(subscribers)} subscriber(s)...")
    sent, failed = 0, 0

    for sub in subscribers:
        email = sub if isinstance(sub, str) else sub.get("email", "")
        if not email:
            continue
        html = build_email_html(posts, summary_date, summary_text, email)
        ok, response = send_email(email, subject, html, text)
        if ok:
            sent += 1
            print(f"  ✓ Sent to {email}")
        else:
            failed += 1
            print(f"  ✗ Failed {email}: {response[:100]}")

    print(f"\n✓ Done. {sent} sent, {failed} failed.")
