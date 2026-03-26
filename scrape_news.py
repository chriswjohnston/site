"""
scrape_news.py - Scrapes township website + 6 Facebook pages via RSSHub
"""
import json, os, re, subprocess, time, requests, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

NEWS_FILE  = Path("src/news.json")
MAX_POSTS  = 100
FB_C_USER  = os.environ.get("FB_C_USER", "")
FB_XS      = os.environ.get("FB_XS", "")
RSSHUB_URL = "http://localhost:1200"

SOURCES = [
    {"label": "Township of Nipissing",        "type": "rss",      "url": "https://nipissingtownship.com/feed/", "priority": 1},
    {"label": "Township of Nipissing",        "type": "facebook", "handle": "Township-of-Nipissing-100064427452575",          "priority": 1},
    {"label": "Nipissing Fire Department",    "type": "facebook", "handle": "Nipissing-Township-Fire-Department-221345511746462", "priority": 2},
    {"label": "Nipissing Recreation",         "type": "facebook", "handle": "NFNRecreation",                                 "priority": 3},
    {"label": "Commanda Community Centre",    "type": "facebook", "handle": "CommandaCommunityCentre",                       "priority": 4},
    {"label": "Nipissing Township Museum",    "type": "facebook", "handle": "Nipissing-Township-Museum-100083092406610",      "priority": 5},
    {"label": "Commanda General Store Museum","type": "facebook", "handle": "commandageneralstoremuseum",                    "priority": 6},
]

def start_rsshub():
    if not FB_C_USER or not FB_XS:
        print("  No Facebook cookies — skipping Facebook sources")
        return None
    print("Starting RSSHub...")
    env = os.environ.copy()
    env["FACEBOOK_COOKIE"] = f"c_user={FB_C_USER}; xs={FB_XS}"
    env["PORT"] = "1200"
    env["NODE_ENV"] = "production"
    env["CACHE_TYPE"] = ""
    proc = subprocess.Popen(
        ["npx", "--yes", "rsshub@latest"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    for i in range(30):
        time.sleep(2)
        try:
            r = requests.get(f"{RSSHUB_URL}/", timeout=3)
            if r.status_code < 500:
                print(f"  RSSHub ready ({i*2+2}s)")
                return proc
        except:
            pass
    print("  RSSHub failed to start")
    proc.kill()
    return None

def stop_rsshub(proc):
    if proc:
        proc.kill()

def clean_html(text):
    if not text: return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def make_fingerprint(text):
    text = re.sub(r"[^a-z0-9\s]", "", text.lower())
    stopwords = {"the","a","an","and","or","in","on","at","to","for","of","with","is","was","are","we","our","it","this","that"}
    words = set(text.split()) - stopwords
    return " ".join(sorted(words))

def similarity(fp1, fp2):
    if not fp1 or not fp2: return 0
    w1, w2 = set(fp1.split()), set(fp2.split())
    if not w1 or not w2: return 0
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
        print(f"  Error {label}: {e}")
    return posts

def deduplicate(posts):
    posts.sort(key=lambda p: (p.get("priority", 99)))
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
    NEWS_FILE.write_text(json.dumps({"updated": datetime.now().strftime("%B %d, %Y"), "posts": posts}, indent=2, ensure_ascii=False))
    print(f"  Saved {len(posts)} posts")

if __name__ == "__main__":
    print("=" * 50)
    print(f"News Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    all_posts = []
    proc = start_rsshub() if (FB_C_USER and FB_XS) else None
    for src in SOURCES:
        if src["type"] == "rss":
            print(f"\nFetching: {src['label']} (RSS)")
            p = parse_rss(src["url"], src["label"], src["priority"])
            print(f"  ✓ {len(p)} posts")
            all_posts.extend(p)
        elif src["type"] == "facebook" and proc:
            print(f"\nFetching: {src['label']} (Facebook)")
            p = parse_rss(f"{RSSHUB_URL}/facebook/page/{src['handle']}", src["label"], src["priority"])
            print(f"  {'✓' if p else '✗'} {len(p)} posts")
            all_posts.extend(p)
    stop_rsshub(proc)
    existing = load_existing()
    existing_fps = {p.get("fingerprint","") for p in existing.get("posts",[])}
    for p in existing.get("posts", []):
        if p.get("fingerprint","") not in {x.get("fingerprint","") for x in all_posts}:
            all_posts.append(p)
    print(f"\nDeduplicating {len(all_posts)} posts...")
    deduped = deduplicate(all_posts)
    print(f"  {len(deduped)} unique | {len([p for p in deduped if p.get('fingerprint','') not in existing_fps])} new")
    save(deduped)
    print("\n✓ Done.")
