"""
build_site.py - Builds docs/ from src/ files
Injects news ticker + signup form into campaign site
"""
import json, os, re, shutil
from pathlib import Path
from datetime import datetime, date

NEWS_FILE      = Path("src/news.json")
CAMPAIGN_SRC   = Path("src/campaign/index.html")
COUNTDOWN_SRC  = Path("src/countdown.html")
DOCS_DIR       = Path("docs")
LAUNCH_DATE    = os.environ.get("LAUNCH_DATE", "2026-10-01")

TICKER_SNIPPET = """  <script src="/components/news-ticker.js" defer></script>
  <style>.ticker-wrap{position:sticky;top:60px;z-index:99;}</style>"""

SIGNUP_HTML = """
<section id="signup" style="background:#F2EAD3;padding:3.5rem 2rem;">
  <div style="max-width:600px;margin:0 auto;text-align:center;">
    <p style="font-size:.68rem;font-weight:700;letter-spacing:.25em;text-transform:uppercase;color:#C06830;margin-bottom:.5rem;">Stay Informed</p>
    <h2 style="font-family:'Playfair Display',serif;font-size:1.8rem;color:#2C4A3E;margin-bottom:.75rem;">Township Updates in Your Inbox</h2>
    <p style="font-size:.95rem;color:#666;margin-bottom:1.5rem;line-height:1.7;">Every two weeks — the latest Nipissing Township news and a summary of the most recent council meeting.</p>
    <form id="signup-form" style="display:flex;gap:.75rem;justify-content:center;flex-wrap:wrap;">
      <input type="email" name="email" placeholder="your@email.com" required
        style="flex:1;min-width:220px;max-width:320px;padding:.75rem 1rem;border:2px solid rgba(44,74,62,.2);border-radius:6px;font-size:.95rem;font-family:inherit;background:#fff;color:#1E2B2A;"
        onfocus="this.style.borderColor='#2C4A3E'" onblur="this.style.borderColor='rgba(44,74,62,.2)'">
      <button type="submit"
        style="background:#C06830;color:#fff;border:none;border-radius:6px;padding:.75rem 1.75rem;font-size:.85rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;font-family:inherit;"
        onmouseover="this.style.background='#A8552A'" onmouseout="this.style.background='#C06830'">Subscribe</button>
    </form>
    <p id="signup-msg" style="margin-top:.75rem;font-size:.85rem;color:#2C4A3E;display:none;"></p>
  </div>
</section>
<script>
document.getElementById('signup-form').addEventListener('submit',async function(e){
  e.preventDefault();
  const email=this.email.value, msg=document.getElementById('signup-msg'), btn=this.querySelector('button');
  btn.textContent='Subscribing\u2026'; btn.disabled=true;
  try{
    const r=await fetch('/.netlify/functions/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
    if(r.ok){msg.textContent='\u2713 Subscribed! Watch your inbox.';msg.style.color='#2C4A3E';msg.style.display='block';this.reset();}
    else throw new Error();
  }catch{msg.textContent='Something went wrong \u2014 please try again.';msg.style.color='#C06830';msg.style.display='block';}
  btn.textContent='Subscribe'; btn.disabled=false;
});
</script>"""

NEWS_PAGE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Lato:wght@300;400;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--forest:#2C4A3E;--pine:#3D6B5E;--warm:#E8C98A;--rust:#C06830;--charcoal:#1E2B2A;--cream:#FAF7F0;--sky:#A8D5E2;--shadow:0 2px 16px rgba(30,43,42,.10)}
body{font-family:'Lato',sans-serif;background:var(--cream);color:var(--charcoal);line-height:1.6}
nav{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:1rem 2.5rem;background:rgba(44,74,62,.97);backdrop-filter:blur(8px);box-shadow:0 2px 20px rgba(0,0,0,.2)}
.nav-logo{font-family:'Playfair Display',serif;font-size:1.1rem;color:var(--warm);text-decoration:none}
.nav-logo span{color:var(--sky)}
.nav-links{display:flex;gap:1.6rem;list-style:none}
.nav-links a{color:rgba(255,255,255,.85);text-decoration:none;font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;transition:color .2s}
.nav-links a:hover{color:var(--warm)}
.page-hero{background:var(--forest);padding:7rem 2rem 3.5rem;border-bottom:4px solid var(--warm)}
.page-hero .inner{max-width:1100px;margin:0 auto}
.page-hero h1{font-family:'Playfair Display',serif;font-size:clamp(2rem,4vw,3.2rem);font-weight:800;color:#fff;line-height:1.1;margin-bottom:.5rem}
.page-hero h1 em{font-style:normal;color:var(--warm)}
.page-hero p{font-size:1rem;font-weight:300;color:rgba(255,255,255,.7);max-width:580px;margin-top:.5rem}
main{max-width:1100px;margin:3rem auto;padding:0 2rem 5rem}
.filters{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1.5rem}
.filter-btn{font-size:.75rem;font-weight:700;padding:.35rem .9rem;border-radius:20px;border:1px solid rgba(44,74,62,.25);background:#fff;color:var(--forest);cursor:pointer;transition:all .15s}
.filter-btn:hover,.filter-btn.active{background:var(--forest);color:#fff;border-color:var(--forest)}
.news-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:1.5rem}
.news-card{background:#fff;border:1px solid rgba(44,74,62,.12);border-top:3px solid var(--pine);border-radius:0 0 10px 10px;padding:1.4rem 1.6rem;box-shadow:var(--shadow);transition:transform .15s,box-shadow .2s}
.news-card:hover{transform:translateY(-3px);box-shadow:0 8px 28px rgba(30,43,42,.14)}
.news-card .meta{font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--rust);margin-bottom:.5rem}
.news-card .source{color:#aaa;font-weight:400}
.news-card h3{font-family:'Playfair Display',serif;font-size:1.05rem;font-weight:700;margin-bottom:.5rem}
.news-card h3 a{color:var(--forest);text-decoration:none;transition:color .15s}
.news-card h3 a:hover{color:var(--rust)}
.news-card p{font-size:.88rem;color:#666;line-height:1.7}
.news-card[data-hidden="true"]{display:none}
footer{background:var(--charcoal);padding:2.5rem 2rem;text-align:center}
footer .inner{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;align-items:center;gap:.75rem}
footer .logo{font-family:'Playfair Display',serif;font-size:1.1rem;color:var(--warm)}
footer .logo span{color:var(--sky)}
footer p{font-size:.8rem;color:rgba(255,255,255,.35)}
footer a{color:var(--warm);text-decoration:none}
@media(max-width:700px){nav{padding:1rem 1.25rem}.nav-links{gap:.8rem}main{padding:0 1.25rem 4rem}.news-grid{grid-template-columns:1fr}}
"""

def is_campaign_mode():
    return date.today().isoformat() >= LAUNCH_DATE

def load_news():
    if NEWS_FILE.exists():
        try: return json.loads(NEWS_FILE.read_text())
        except: pass
    return {"posts": []}

def get_sources(posts):
    seen, sources = set(), []
    for p in posts:
        s = p.get("source", "")
        if s and s not in seen:
            seen.add(s)
            sources.append(s)
    return sources

def build_news_page(posts):
    sources = get_sources(posts)
    filter_btns = '<button class="filter-btn active" onclick="filterNews(this,\'all\')">All Sources</button>'
    for s in sources:
        filter_btns += f'<button class="filter-btn" onclick="filterNews(this,\'{s}\')">{s}</button>'

    cards = ""
    for p in posts:
        source = p.get("source", "")
        cards += f"""
    <div class="news-card" data-source="{source}">
      <div class="meta">{p.get('date','')} <span class="source">· {source}</span></div>
      <h3><a href="{p['url']}" target="_blank" rel="noopener">{p['title']}</a></h3>
      {f'<p>{p["excerpt"]}</p>' if p.get('excerpt') else ''}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Township News – chriswjohnston.ca</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <style>{NEWS_PAGE_CSS}</style>
</head>
<body>
<nav>
  <a class="nav-logo" href="/">Chris <span>Johnston</span></a>
  <ul class="nav-links">
    <li><a href="/#priorities">Priorities</a></li>
    <li><a href="/news/">News</a></li>
    <li><a href="/#contact">Contact</a></li>
    <li><a href="https://council.chriswjohnston.ca" style="color:var(--warm);">Council Archive</a></li>
  </ul>
</nav>
<div class="page-hero"><div class="inner">
  <p style="font-size:.7rem;font-weight:700;letter-spacing:.25em;text-transform:uppercase;color:var(--warm);margin-bottom:.8rem;">Nipissing Township</p>
  <h1>Community <em>News</em></h1>
  <p>Posts from the Township and local community pages, updated daily.</p>
</div></div>
<main>
  <div class="filters">{filter_btns}</div>
  <div class="news-grid" id="news-grid">{cards}</div>
</main>
<footer><div class="inner">
  <div class="logo">Chris <span>Johnston</span></div>
  <p>News sourced from nipissingtownship.com and local Facebook pages · Updated daily</p>
</div></footer>
<script>
function filterNews(btn, source) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.news-card').forEach(card => {{
    card.dataset.hidden = (source !== 'all' && card.dataset.source !== source) ? 'true' : 'false';
  }});
}}
</script>
</body></html>"""

def inject_into_campaign(html, posts):
    # Add ticker script to head
    html = html.replace("</head>", TICKER_SNIPPET + "\n</head>", 1)
    # Add ticker bar after nav
    ticker = '\n<div class="ticker-wrap"><news-ticker src="/news.json" count="5" speed="45"></news-ticker></div>\n'
    html = re.sub(r'(</nav>)', r'\1' + ticker, html, count=1)
    # Add news link to nav
    html = html.replace(
        '<li><a href="#contact">Contact</a></li>',
        '<li><a href="#contact">Contact</a></li>\n    <li><a href="/news/">News</a></li>', 1
    )
    # Inject signup before contact section
    html = html.replace('<section id="contact">', SIGNUP_HTML + '\n<section id="contact">', 1)
    return html

def build():
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "components").mkdir(exist_ok=True)
    (DOCS_DIR / "news").mkdir(exist_ok=True)

    # Copy ticker component
    ticker_src = Path("news-ticker.js")
    if ticker_src.exists():
        shutil.copy(ticker_src, DOCS_DIR / "components" / "news-ticker.js")
        print("  ✓ news-ticker.js")

    # Copy news.json
    news_data = load_news()
    posts = news_data.get("posts", [])
    (DOCS_DIR / "news.json").write_text(json.dumps(news_data, indent=2, ensure_ascii=False))
    print(f"  ✓ news.json ({len(posts)} posts)")

    # Build news page
    (DOCS_DIR / "news" / "index.html").write_text(build_news_page(posts), encoding="utf-8")
    print("  ✓ news/index.html")

    # Build index
    mode = "campaign" if is_campaign_mode() else "countdown"
    print(f"  Mode: {mode} (launch: {LAUNCH_DATE})")
    if mode == "campaign" and CAMPAIGN_SRC.exists():
        html = inject_into_campaign(CAMPAIGN_SRC.read_text(encoding="utf-8"), posts)
        (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
        print("  ✓ index.html (campaign + ticker + signup)")
    elif COUNTDOWN_SRC.exists():
        shutil.copy(COUNTDOWN_SRC, DOCS_DIR / "index.html")
        print("  ✓ index.html (countdown)")

    print("\n✓ Build complete.")

if __name__ == "__main__":
    print("=" * 50)
    print(f"Site Builder — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    build()
