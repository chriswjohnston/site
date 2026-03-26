"""
Nipissing Township News Scraper
================================
Scrapes the township WordPress RSS feed, saves to src/news.json
Run daily via GitHub Actions.
"""

import json
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

NEWS_FILE   = Path("src/news.json")
SOURCE_URL  = "https://nipissingtownship.com"
FEED_URL    = f"{SOURCE_URL}/feed/"
MAX_POSTS   = 50  # keep up to 50 posts in the archive

def clean_html(text):
    """Strip HTML tags and clean up whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def fetch_posts():
    print(f"Fetching {FEED_URL} ...")
    try:
        resp = requests.get(FEED_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        print(f"  RSS fetch failed: {e}")
        # Fall back to scraping the homepage
        return fetch_posts_from_html()

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  RSS parse failed: {e}")
        return fetch_posts_from_html()

    channel = root.find("channel")
    if channel is None:
        return fetch_posts_from_html()

    posts = []
    for item in channel.findall("item"):
        title   = item.findtext("title", "").strip()
        link    = item.findtext("link", "").strip()
        pub_raw = item.findtext("pubDate", "")
        desc    = item.findtext("description", "")

        # Try content:encoded for full post
        content_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
        content = content_el.text if content_el is not None else desc

        # Parse date
        try:
            pub_dt  = parsedate_to_datetime(pub_raw)
            pub_iso = pub_dt.strftime("%Y-%m-%d")
            pub_fmt = pub_dt.strftime("%B %d, %Y")
        except Exception:
            pub_iso = ""
            pub_fmt = pub_raw[:16] if pub_raw else ""

        # Build excerpt — first 200 chars of clean text
        excerpt = clean_html(content)[:200].strip()
        if excerpt and not excerpt.endswith("."):
            excerpt = excerpt.rsplit(" ", 1)[0] + "…"

        if title and link:
            posts.append({
                "title":   title,
                "url":     link,
                "date":    pub_fmt,
                "date_iso": pub_iso,
                "excerpt": excerpt,
            })

    print(f"  Found {len(posts)} posts via RSS")
    return posts[:MAX_POSTS]


def fetch_posts_from_html():
    """Fallback: scrape the WordPress homepage post list."""
    from bs4 import BeautifulSoup
    print("  Falling back to HTML scrape...")
    posts = []
    try:
        resp = requests.get(SOURCE_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for article in soup.find_all(["article", "div"], class_=re.compile(r"post|entry|hentry")):
            title_el = article.find(["h1","h2","h3","h4"])
            link_el  = article.find("a", href=True)
            date_el  = article.find(["time", "span"], class_=re.compile(r"date|time|posted"))
            if title_el and link_el:
                href = link_el["href"]
                if not href.startswith("http"):
                    href = SOURCE_URL + href
                posts.append({
                    "title":    title_el.get_text(strip=True),
                    "url":      href,
                    "date":     date_el.get_text(strip=True) if date_el else "",
                    "date_iso": "",
                    "excerpt":  "",
                })
        print(f"  Found {len(posts)} posts via HTML scrape")
    except Exception as e:
        print(f"  HTML scrape also failed: {e}")
    return posts[:MAX_POSTS]


def load_existing():
    if NEWS_FILE.exists():
        try:
            return json.loads(NEWS_FILE.read_text())
        except:
            pass
    return {"posts": [], "updated": ""}


def save(posts):
    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "updated": datetime.now().strftime("%B %d, %Y"),
        "source":  SOURCE_URL,
        "posts":   posts,
    }
    NEWS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  Saved {len(posts)} posts to {NEWS_FILE}")


if __name__ == "__main__":
    print("=" * 50)
    print("Nipissing News Scraper")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    existing = load_existing()
    existing_urls = {p["url"] for p in existing.get("posts", [])}

    fresh = fetch_posts()

    # Merge: new posts first, then existing ones not already in fresh
    fresh_urls = {p["url"] for p in fresh}
    merged = fresh + [p for p in existing.get("posts", []) if p["url"] not in fresh_urls]
    merged = merged[:MAX_POSTS]

    new_count = len([p for p in fresh if p["url"] not in existing_urls])
    print(f"  {new_count} new post(s) found")
    save(merged)
    print("✓ Done.")
