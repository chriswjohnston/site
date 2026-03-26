"""
scrape_news.py
==============
Scrapes township RSS feed + Facebook public pages directly using session cookies.
No RSSHub needed. Saves deduplicated results to src/news.json.
"""
import json, os, re, requests, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

NEWS_FILE = Path("src/news.json")
MAX_POSTS = 100
FB_C_USER = os.environ.get("FB_C_USER", "")
FB_XS     = os.environ.get("FB_XS", "")

SOURCES = [
    {"label": "Township of Nipissing",         "type": "rss",      "url": "https://nipissingtownship.com/feed/", "priority": 1},
    {"label": "Township of Nipissing",         "type": "facebook", "handle": "Township-of-Nipissing-100064427452575",             "priority": 1},
    {"label": "Nipissing Fire Department",     "type": "facebook", "handle": "Nipissing-Township-Fire-Department-221345511746462","priority": 2},
    {"label": "Nipissing Recreation",          "type": "facebook", "handle": "NFNRecreation",                                    "priority": 3},
    {"label": "Commanda Community Centre",     "type": "facebook", "handle": "CommandaCommunityCentre",                          "priority": 4},
    {"label": "Nipissing Township Museum",     "type": "facebook", "handle": "Nipissing-Township-Museum-100083092406610",         "priority": 5},
    {"label": "Commanda General Store Museum", "type": "facebook", "handle": "commandageneralstoremuseum",                       "priority": 6},
]

FB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def fb_cookies():
    if not FB_C_USER or not FB_XS:
        return None
    xs = FB_XS.replace("%3A", ":").replace("%2C", ",")
    return {"c_user": FB_C_USER, "xs": xs}

def clean_html(text):
    if not text: return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    return re.sub(r"\s+", " ", text).strip()

def make_fingerprint(text):
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    stopwords = {"the","a","an","and","or","in","on","at","to","for","of","with",
                 "is","was","are","we","our","it","this","that","be","has","have"}
    words = set(text.split()) - stopwords
    return " ".join(sorted(words))

def similarity(fp1, fp2):
    if not fp1 or not fp2: return 0.0
    w1, w2 = set(fp1.split()), set(fp2.split())
    if not w1 or not w2: return 0.0
    return len(w1 & w2) / len(w1 | w2)

def parse_rss(url, label, priority):
    posts = []
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if not channel: return posts
        for item in channel.findall("item"):
            title   = item.findtext("title", "").strip()
            link    = item.findtext("link", "").strip()
            pub_raw = item.findtext("pubDate", "")
            desc    = item.findtext("description", "")
            ce      = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            content = ce.text if ce is not None else desc
            try:
                dt = parsedate_to_datetime(pub_raw)
                pub_iso, pub_fmt = dt.strftime("%Y-%m-%d"), dt.strftime("%B %d, %Y")
            except:
                pub_iso, pub_fmt = "", ""
            excerpt = clean_html(content)[:220].strip()
            if excerpt and not excerpt.endswith((".", "!", "?")):
                excerpt = excerpt.rsplit(" ", 1)[0] + "…"
            if title and link:
                posts.append({
                    "title": title, "url": link, "date": pub_fmt,
                    "date_iso": pub_iso, "excerpt": excerpt,
                    "source": label, "priority": priority,
                    "fingerprint": make_fingerprint(title + " " + clean_html(desc)),
                })
    except Exception as e:
        print(f"  RSS error ({label}): {e}")
    return posts

def scrape_facebook_page(handle, label, priority):
    """Scrape a public Facebook page directly using session cookies."""
    cookies = fb_cookies()
    if not cookies:
        print(f"  Skipping {label} — no Facebook cookies")
        return []

    url = f"https://www.facebook.com/{handle}"
    posts = []
    try:
        resp = requests.get(url, headers=FB_HEADERS, cookies=cookies, timeout=20)
        if resp.status_code != 200:
            print(f"  Facebook {handle}: HTTP {resp.status_code}")
            return []

        html = resp.text

        # Extract post text blocks from the page JSON data
        # Facebook embeds page data as JSON in script tags
        json_blocks = re.findall(r'{"__typename":"Story"[^}]{0,2000}?"message":\{"text":"([^"]{10,500})"', html)
        if not json_blocks:
            # Fallback: look for data-ad-preview blocks
            json_blocks = re.findall(r'"message":\{"text":"([^"]{10,500})"', html)

        # Extract post URLs
        post_urls = re.findall(r'href="(https://www\.facebook\.com/' + re.escape(handle.split('-')[0]) + r'[^"]*(?:posts|videos|photos)[^"]*)"', html)
        post_urls = list(dict.fromkeys(post_urls))  # deduplicate preserving order

        # Extract dates
        dates = re.findall(r'"publish_time":(\d+)', html)

        for i, text in enumerate(json_blocks[:10]):
            text = text.encode().decode('unicode_escape') if '\\u' in text else text
            text = re.sub(r'\\n', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) < 15:
                continue

            post_url = post_urls[i] if i < len(post_urls) else url
            # Clean up Facebook tracking params
            post_url = re.sub(r'\?.*$', '', post_url)

            try:
                ts = int(dates[i]) if i < len(dates) else 0
                dt = datetime.fromtimestamp(ts) if ts else datetime.now()
                pub_iso = dt.strftime("%Y-%m-%d")
                pub_fmt = dt.strftime("%B %d, %Y")
            except:
                pub_iso, pub_fmt = "", ""

            # Use first line as title, rest as excerpt
            lines = [l.strip() for l in text.split('. ') if l.strip()]
            title = lines[0][:120] if lines else text[:120]
            excerpt = text[:220] + "…" if len(text) > 220 else text

            posts.append({
                "title": title,
                "url": post_url,
                "date": pub_fmt,
                "date_iso": pub_iso,
                "excerpt": excerpt,
                "source": label,
                "priority": priority,
                "fingerprint": make_fingerprint(text),
            })

        print(f"  ✓ {label}: {len(posts)} posts")
    except Exception as e:
        print(f"  Facebook error ({handle}): {e}")
    return posts

def deduplicate(posts):
    posts.sort(key=lambda p: p.get("priority", 99))
    kept = []
    for post in posts:
        fp = post.get("fingerprint", "")
        dup = False
        for k in kept:
            if similarity(fp, k.get("fingerprint", "")) > 0.75:
                dup = True
                if post.get("priority", 99) < k.get("priority", 99):
                    kept.remove(k)
                    kept.append(post)
                break
        if not dup:
            kept.append(post)
    def sk(p):
        try: return datetime.strptime(p["date_iso"], "%Y-%m-%d")
        except: return datetime.min
    kept.sort(key=sk, reverse=True)
    return kept[:MAX_POSTS]

def load_existing():
    if NEWS_FILE.exists():
        try: return json.loads(NEWS_FILE.read_text())
        except: pass
    return {"posts": []}

def save(posts):
    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps({
        "updated": datetime.now().strftime("%B %d, %Y"),
        "posts": posts
    }, indent=2, ensure_ascii=False))
    print(f"  Saved {len(posts)} posts to {NEWS_FILE}")

if __name__ == "__main__":
    print("=" * 50)
    print(f"News Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    all_posts = []
    for src in SOURCES:
        print(f"\nFetching: {src['label']} ({src['type']})")
        if src["type"] == "rss":
            p = parse_rss(src["url"], src["label"], src["priority"])
        else:
            p = scrape_facebook_page(src["handle"], src["label"], src["priority"])
        all_posts.extend(p)

    existing = load_existing()
    existing_fps = {p.get("fingerprint", "") for p in existing.get("posts", [])}
    for p in existing.get("posts", []):
        if p.get("fingerprint", "") not in {x.get("fingerprint", "") for x in all_posts}:
            all_posts.append(p)

    print(f"\nDeduplicating {len(all_posts)} posts...")
    deduped = deduplicate(all_posts)
    new_count = len([p for p in deduped if p.get("fingerprint", "") not in existing_fps])
    print(f"  {len(deduped)} unique | {new_count} new")
    save(deduped)
    print("\n✓ Done.")
