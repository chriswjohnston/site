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
    {"label": "Township of Nipissing",         "type": "facebook", "handle": "Township-of-Nipissing-100064427452575",              "priority": 1},
    {"label": "Nipissing Fire Department",     "type": "facebook", "handle": "Nipissing-Township-Fire-Department-221345511746462", "priority": 2},
    {"label": "Nipissing Recreation",          "type": "facebook", "handle": "NFNRecreation",                                     "priority": 3},
    {"label": "Commanda Community Centre",     "type": "facebook", "handle": "CommandaCommunityCentre",                           "priority": 4},
    {"label": "Nipissing Township Museum",     "type": "facebook", "handle": "Nipissing-Township-Museum-100083092406610",          "priority": 5},
    {"label": "Commanda General Store Museum", "type": "facebook", "handle": "commandageneralstoremuseum",                        "priority": 6},
]

FB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

# ── helpers ────────────────────────────────────────────────────────────────────

def fb_cookies():
    if not FB_C_USER or not FB_XS:
        return None
    xs = FB_XS.replace("%3A", ":").replace("%2C", ",")
    return {"c_user": FB_C_USER, "xs": xs}

def clean_html(text):
    if not text: return ""
    text = re.sub(r"<[^>]+>", " ", text)
    for esc, ch in [("&amp;","&"),("&lt;","<"),("&gt;",">"),("&nbsp;"," ")]:
        text = text.replace(esc, ch)
    text = re.sub(r"&#\d+;", "", text)
    return re.sub(r"\s+", " ", text).strip()

def unescape_fb(text):
    """Decode Facebook's JSON unicode escapes and common replacements."""
    try:
        text = text.encode("utf-8").decode("unicode_escape")
    except Exception:
        pass
    text = re.sub(r"\\n", " ", text)
    text = re.sub(r"\\u[\da-fA-F]{4}", lambda m: chr(int(m.group(0)[2:], 16)), text)
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

def excerpt_from(text, max_len=220):
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"

def title_from(text):
    """First sentence or first 120 chars, whichever is shorter."""
    for sep in (".\n", "!\n", "?\n", "\n", ". ", "! ", "? "):
        idx = text.find(sep)
        if 20 < idx < 120:
            return text[:idx + 1].strip()
    return text[:120].rsplit(" ", 1)[0].strip()

# ── RSS ────────────────────────────────────────────────────────────────────────

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
                pub_iso = dt.strftime("%Y-%m-%d")
                pub_fmt = dt.strftime("%B %d, %Y")
            except Exception:
                pub_iso = pub_fmt = ""
            exc = excerpt_from(clean_html(content))
            if title and link:
                posts.append({
                    "title": title, "url": link, "date": pub_fmt,
                    "date_iso": pub_iso, "excerpt": exc,
                    "source": label, "priority": priority,
                    "fingerprint": make_fingerprint(title + " " + clean_html(desc)),
                })
    except Exception as e:
        print(f"  RSS error ({label}): {e}")
    return posts

# ── Facebook ───────────────────────────────────────────────────────────────────

def _extract_json_blobs(html):
    """
    Pull every JSON object that sits inside a <script> tag and
    contains a 'message' key — these hold the post text on modern FB.
    Returns a list of dicts (already parsed).
    """
    blobs = []
    # Find all script-tag contents
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html)
    for s in scripts:
        # Only bother with scripts that mention "message" or "story_message"
        if '"message"' not in s and '"story_message"' not in s:
            continue
        # Facebook often uses ]]> or requires stripping cruft
        s = re.sub(r"^[^{[]*", "", s).strip()
        # Try to parse any JSON object/array in here
        for match in re.finditer(r"\{[^{}]{20,}", s):
            try:
                obj = json.loads(match.group(0) + "}")
                blobs.append(obj)
            except Exception:
                pass
    return blobs

def _find_in_blob(obj, key, results=None, depth=0):
    """Recursively find all values for a given key in a nested dict/list."""
    if results is None:
        results = []
    if depth > 12:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                results.append(v)
            else:
                _find_in_blob(v, key, results, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _find_in_blob(item, key, results, depth + 1)
    return results

def _regex_extract_posts(html, page_url):
    """
    Multi-strategy regex fallback for when JSON parsing doesn't yield results.
    Returns list of (text, timestamp, post_url) tuples.
    """
    results = []

    # Strategy 1: "message":{"text":"..."} pattern (most common in 2024/2025 FB HTML)
    for m in re.finditer(r'"message"\s*:\s*\{"text"\s*:\s*"((?:[^"\\]|\\.){{10,500}})"', html):
        results.append((m.group(1), 0, page_url))

    # Strategy 2: story_message
    if not results:
        for m in re.finditer(r'"story_message"\s*:\s*\{"text"\s*:\s*"((?:[^"\\]|\\.){{10,500}})"', html):
            results.append((m.group(1), 0, page_url))

    # Strategy 3: bare "text" inside a post-looking context
    if not results:
        for m in re.finditer(r'"creation_time"\s*:\s*(\d+).*?"text"\s*:\s*"((?:[^"\\]|\\.){20,400})"', html):
            results.append((m.group(2), int(m.group(1)), page_url))

    # Strategy 4: mbasic (mobile basic) plain-text paragraphs
    if not results:
        for m in re.finditer(r'<div[^>]*data-ft[^>]*>.*?<p>([\s\S]{20,400}?)</p>', html):
            results.append((clean_html(m.group(1)), 0, page_url))

    return results[:12]

def scrape_facebook_page(handle, label, priority):
    """Scrape a public Facebook page using session cookies, with multiple fallbacks."""
    cookies = fb_cookies()
    if not cookies:
        print(f"  Skipping {label} — no Facebook cookies")
        return []

    posts = []

    # Try normal page first, fall back to mbasic (plain HTML, much easier to parse)
    for base_url in [
        f"https://www.facebook.com/{handle}",
        f"https://mbasic.facebook.com/{handle}",
    ]:
        try:
            resp = requests.get(
                base_url, headers=FB_HEADERS, cookies=cookies,
                timeout=25, allow_redirects=True
            )
            if resp.status_code == 302 or "login" in resp.url:
                print(f"  {label}: redirected to login — cookies may be expired")
                break
            if resp.status_code != 200:
                print(f"  {label} ({base_url}): HTTP {resp.status_code}")
                continue

            html = resp.text
            is_mbasic = "mbasic" in base_url

            # ── mbasic path: much cleaner HTML ──────────────────────────────
            if is_mbasic:
                # Posts appear as <div> blocks with an <abbr> timestamp and <p> text
                story_pattern = re.finditer(
                    r'<div[^>]*>([\s\S]{20,600}?)</div>\s*<div[^>]*>\s*<a[^>]*>(?:Like|Comment)',
                    html
                )
                timestamps = re.findall(r'data-store="[^"]*"data-time="(\d+)"', html)
                ts_list = [int(t) for t in timestamps]

                raw_texts = []
                for m in re.finditer(r'<p>([\s\S]{15,500}?)</p>', html):
                    raw_texts.append(clean_html(m.group(1)))

                post_links = re.findall(
                    r'href="(https://mbasic\.facebook\.com/' + re.escape(handle.split('-')[0]) +
                    r'[^"]*(?:posts|story|permalink)[^"]*)"', html
                )
                post_links = [re.sub(r'\?.*$', '', l.replace("mbasic.", "www.")) for l in post_links]

                for i, text in enumerate(raw_texts[:10]):
                    if len(text) < 15:
                        continue
                    ts = ts_list[i] if i < len(ts_list) else 0
                    try:
                        dt = datetime.fromtimestamp(ts) if ts else datetime.now()
                    except Exception:
                        dt = datetime.now()
                    post_url = post_links[i] if i < len(post_links) else f"https://www.facebook.com/{handle}"
                    posts.append(_build_post(text, dt, post_url, label, priority))

            # ── desktop path: JSON blobs or regex ───────────────────────────
            else:
                # Try JSON blob extraction first
                texts_with_meta = []

                # Pull timestamps
                timestamps = [int(t) for t in re.findall(r'"publish_time"\s*:\s*(\d+)', html)]
                # Pull post URLs
                post_urls = re.findall(
                    r'"(https://www\.facebook\.com/' + re.escape(handle.split('-')[0]) +
                    r'[^"]*(?:posts|videos|photos|permalink)[^"]*)"', html
                )
                post_urls = list(dict.fromkeys(
                    re.sub(r'\?[^"]*', '', u) for u in post_urls
                ))

                # Extract message texts via regex (most reliable on desktop FB)
                text_matches = re.findall(
                    r'"message"\s*:\s*\{"text"\s*:\s*"((?:[^"\\]|\\.){10,800})"',
                    html
                )
                if not text_matches:
                    text_matches = re.findall(
                        r'"story_message"\s*:\s*\{"text"\s*:\s*"((?:[^"\\]|\\.){10,800})"',
                        html
                    )

                for i, raw in enumerate(text_matches[:10]):
                    text = unescape_fb(raw)
                    if len(text) < 15:
                        continue
                    ts = timestamps[i] if i < len(timestamps) else 0
                    try:
                        dt = datetime.fromtimestamp(ts) if ts else datetime.now()
                    except Exception:
                        dt = datetime.now()
                    post_url = post_urls[i] if i < len(post_urls) else f"https://www.facebook.com/{handle}"
                    posts.append(_build_post(text, dt, post_url, label, priority))

                # If we got nothing, try mbasic fallback next iteration
                if not posts:
                    print(f"  {label}: desktop parse empty, trying mbasic…")
                    continue

            if posts:
                print(f"  ✓ {label}: {len(posts)} posts (via {'mbasic' if is_mbasic else 'desktop'})")
                break  # success — don't try the other URL

        except Exception as e:
            print(f"  Facebook error ({handle} @ {base_url}): {e}")
            continue

    if not posts:
        print(f"  ✗ {label}: 0 posts extracted — cookies may need refreshing")

    return posts

def _build_post(text, dt, url, label, priority):
    pub_iso = dt.strftime("%Y-%m-%d")
    pub_fmt = dt.strftime("%B %d, %Y")
    return {
        "title":       title_from(text),
        "url":         url,
        "date":        pub_fmt,
        "date_iso":    pub_iso,
        "excerpt":     excerpt_from(text),
        "source":      label,
        "priority":    priority,
        "fingerprint": make_fingerprint(text),
    }

# ── deduplication & persistence ────────────────────────────────────────────────

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
        try:   return datetime.strptime(p["date_iso"], "%Y-%m-%d")
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
    print(f"  Saved {len(posts)} posts → {NEWS_FILE}")

# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print(f"News Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    all_posts = []
    for src in SOURCES:
        print(f"\nFetching: {src['label']} ({src['type']})")
        if src["type"] == "rss":
            p = parse_rss(src["url"], src["label"], src["priority"])
        else:
            p = scrape_facebook_page(src["handle"], src["label"], src["priority"])
        print(f"  → {len(p)} posts fetched")
        all_posts.extend(p)

    # Merge with existing so we don't lose older posts not on the page today
    existing = load_existing()
    existing_fps = {p.get("fingerprint", "") for p in existing.get("posts", [])}
    new_fps = {p.get("fingerprint", "") for p in all_posts}
    for p in existing.get("posts", []):
        if p.get("fingerprint", "") not in new_fps:
            all_posts.append(p)

    print(f"\nDeduplicating {len(all_posts)} posts…")
    deduped = deduplicate(all_posts)
    new_count = len([p for p in deduped if p.get("fingerprint", "") not in existing_fps])
    print(f"  {len(deduped)} unique | {new_count} new this run")

    save(deduped)
    print("\n✓ Done.")
