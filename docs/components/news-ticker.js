/**
 * <news-ticker> Web Component
 * ============================
 * Drop into any page with:
 *   <script src="/components/news-ticker.js"></script>
 *   <news-ticker src="/news.json" count="5"></news-ticker>
 *
 * Attributes:
 *   src    — path to news.json  (default: /news.json)
 *   count  — number of items    (default: 5)
 *   speed  — scroll speed px/s  (default: 40)
 */

class NewsTicker extends HTMLElement {
  connectedCallback() {
    const src   = this.getAttribute("src")   || "/news.json";
    const count = parseInt(this.getAttribute("count") || "5", 10);
    const speed = parseInt(this.getAttribute("speed") || "40", 10);

    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          background: #1E2B2A;
          border-top: 2px solid #E8C98A;
          border-bottom: 2px solid #E8C98A;
          overflow: hidden;
          height: 42px;
          position: relative;
          font-family: 'Lato', Arial, sans-serif;
        }
        .label {
          position: absolute;
          left: 0; top: 0; bottom: 0;
          z-index: 2;
          background: #E8C98A;
          color: #1E2B2A;
          font-size: 0.65rem;
          font-weight: 700;
          letter-spacing: 0.15em;
          text-transform: uppercase;
          padding: 0 14px;
          display: flex;
          align-items: center;
          white-space: nowrap;
        }
        .label::after {
          content: '';
          position: absolute;
          right: -10px;
          top: 0; bottom: 0;
          width: 10px;
          background: linear-gradient(to right, #E8C98A, transparent);
        }
        .track-wrap {
          position: absolute;
          left: 120px; right: 0; top: 0; bottom: 0;
          overflow: hidden;
        }
        .track {
          display: flex;
          align-items: center;
          height: 100%;
          white-space: nowrap;
          will-change: transform;
        }
        .item {
          display: inline-flex;
          align-items: center;
          gap: 0;
          padding: 0 32px 0 0;
          color: rgba(255,255,255,0.85);
          font-size: 0.82rem;
          line-height: 1;
        }
        .item a {
          color: inherit;
          text-decoration: none;
          transition: color 0.2s;
        }
        .item a:hover {
          color: #E8C98A;
        }
        .sep {
          display: inline-block;
          width: 4px;
          height: 4px;
          border-radius: 50%;
          background: #E8C98A;
          opacity: 0.5;
          margin-right: 32px;
          vertical-align: middle;
        }
        .date {
          font-size: 0.7rem;
          color: rgba(255,255,255,0.35);
          margin-right: 8px;
        }
        .loading {
          padding: 0 20px;
          font-size: 0.82rem;
          color: rgba(255,255,255,0.4);
          line-height: 42px;
        }
      </style>
      <div class="label">Township News</div>
      <div class="track-wrap">
        <div class="track" id="track">
          <span class="loading">Loading…</span>
        </div>
      </div>
    `;

    this._fetchAndAnimate(src, count, speed);
  }

  async _fetchAndAnimate(src, count, speed) {
    const track = this.shadowRoot.getElementById("track");
    let posts = [];

    try {
      const resp = await fetch(src);
      const data = await resp.json();
      posts = (data.posts || []).slice(0, count);
    } catch (e) {
      track.innerHTML = '<span class="loading">Unable to load news.</span>';
      return;
    }

    if (!posts.length) {
      track.innerHTML = '<span class="loading">No recent posts.</span>';
      return;
    }

    // Build items (duplicated for seamless loop)
    const makeItems = () => posts.map((p, i) => `
      <span class="item">
        ${p.date ? `<span class="date">${p.date}</span>` : ""}
        <a href="${p.url}" target="_blank" rel="noopener">${p.title}</a>
      </span>
      ${i < posts.length - 1 ? '<span class="sep"></span>' : ""}
    `).join("");

    track.innerHTML = makeItems() + makeItems(); // duplicate for loop

    // Measure and animate
    const totalWidth = track.scrollWidth / 2;
    let pos = 0;
    let lastTime = null;
    let paused = false;

    track.addEventListener("mouseenter", () => paused = true);
    track.addEventListener("mouseleave", () => paused = false);

    const tick = (ts) => {
      if (lastTime !== null && !paused) {
        const delta = (ts - lastTime) / 1000;
        pos += speed * delta;
        if (pos >= totalWidth) pos -= totalWidth;
        track.style.transform = `translateX(${-pos}px)`;
      }
      lastTime = ts;
      requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }
}

customElements.define("news-ticker", NewsTicker);
