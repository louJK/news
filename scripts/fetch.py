#!/usr/bin/env python3
"""
NewsDigest Fetcher — Thu thập RSS + tóm tắt bằng Gemini API (tiếng Việt)
Chạy: python scripts/fetch.py
Output: public/data/YYYY-MM-DD.json
"""

import json
import os
import time
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# ── Cấu hình ───────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_DIR = Path("public/data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
OUTPUT_FILE = OUTPUT_DIR / f"{TODAY}.json"

MAX_ITEMS_PER_SOURCE = 8   # số tin tối đa mỗi nguồn
GEMINI_DELAY = 1.5         # giây giữa các API call

# ── Nguồn tin (giữ nguyên theo bản gốc) ────────────────────────────────────
SOURCES = [
    # AI & Tech
    {"id": "hackernews",    "name": "Hacker News",        "category": "Tech",  "url": "https://hnrss.org/frontpage?count=15"},
    {"id": "techcrunch",    "name": "TechCrunch",         "category": "Tech",  "url": "https://techcrunch.com/feed/"},
    {"id": "theVerge",      "name": "The Verge",          "category": "Tech",  "url": "https://www.theverge.com/rss/index.xml"},
    {"id": "wired",         "name": "Wired",              "category": "Tech",  "url": "https://www.wired.com/feed/rss"},
    {"id": "arstechnica",   "name": "Ars Technica",       "category": "Tech",  "url": "https://feeds.arstechnica.com/arstechnica/index"},
    # AI chuyên sâu
    {"id": "openai_blog",   "name": "OpenAI Blog",        "category": "AI",    "url": "https://openai.com/blog/rss/"},
    {"id": "anthropic",     "name": "Anthropic Blog",     "category": "AI",    "url": "https://www.anthropic.com/rss.xml"},
    {"id": "huggingface",   "name": "HuggingFace Blog",   "category": "AI",    "url": "https://huggingface.co/blog/feed.xml"},
    {"id": "deepmind",      "name": "Google DeepMind",    "category": "AI",    "url": "https://deepmind.google/blog/rss.xml"},
    {"id": "mit_ai",        "name": "MIT Technology Review AI", "category": "AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
    # GitHub Trending (dùng unofficial RSS)
    {"id": "github_trending","name": "GitHub Trending",   "category": "Dev",   "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml"},
    # Dev
    {"id": "devto",         "name": "Dev.to",             "category": "Dev",   "url": "https://dev.to/feed"},
    {"id": "lobsters",      "name": "Lobsters",           "category": "Dev",   "url": "https://lobste.rs/rss"},
    # Reddit (JSON API)
    {"id": "r_machinelearning","name": "r/MachineLearning","category": "AI",   "url": "https://www.reddit.com/r/MachineLearning/hot.json?limit=10", "type": "reddit"},
    {"id": "r_localllama",  "name": "r/LocalLLaMA",       "category": "AI",    "url": "https://www.reddit.com/r/LocalLLaMA/hot.json?limit=10", "type": "reddit"},
    {"id": "r_comfyui",     "name": "r/comfyui",          "category": "AI",    "url": "https://www.reddit.com/r/comfyui/hot.json?limit=10", "type": "reddit"},
    {"id": "r_aiart",       "name": "r/AIArt",            "category": "AI",    "url": "https://www.reddit.com/r/AIArt/hot.json?limit=10", "type": "reddit"},
    {"id": "r_webdev",      "name": "r/webdev",           "category": "Dev",   "url": "https://www.reddit.com/r/webdev/hot.json?limit=10", "type": "reddit"},
]

# ── RSS Parser ──────────────────────────────────────────────────────────────
def fetch_url(url, is_reddit=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NewsDigest/1.0; +https://github.com/newsdigest)",
        "Accept": "application/json, application/xml, text/xml, */*",
    }
    if is_reddit:
        headers["User-Agent"] = "NewsDigest:v1.0 (by /u/newsdigest_bot)"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  ❌ Fetch error: {e}")
        return None

def parse_rss(content, source):
    items = []
    try:
        # Strip namespace declarations to simplify parsing
        content_clean = re.sub(r' xmlns[^"]*"[^"]*"', '', content)
        root = ET.fromstring(content_clean)

        # Support both RSS and Atom
        ns = {}
        entries = root.findall(".//item") or root.findall(".//entry")

        for entry in entries[:MAX_ITEMS_PER_SOURCE]:
            title = (
                _get_text(entry, "title") or
                _get_text(entry, "title", ns)
            )
            link = (
                _get_text(entry, "link") or
                entry.find("link").get("href", "") if entry.find("link") is not None else ""
            )
            desc = (
                _get_text(entry, "description") or
                _get_text(entry, "summary") or
                _get_text(entry, "content") or ""
            )
            pub_date = (
                _get_text(entry, "pubDate") or
                _get_text(entry, "published") or
                _get_text(entry, "updated") or ""
            )

            if not title or not link:
                continue

            # Clean HTML từ description
            desc_clean = re.sub(r"<[^>]+>", " ", desc)
            desc_clean = re.sub(r"\s+", " ", desc_clean).strip()[:500]

            item_id = hashlib.md5(link.encode()).hexdigest()[:12]
            items.append({
                "id": item_id,
                "title": title.strip(),
                "url": link.strip(),
                "description": desc_clean,
                "source": source["id"],
                "sourceName": source["name"],
                "category": source["category"],
                "publishedAt": pub_date,
                "summary_vi": "",   # Tóm tắt tiếng Việt (Gemini)
                "summary_en": "",   # Tóm tắt tiếng Anh (Gemini)
                "score": 0,
            })
    except Exception as e:
        print(f"  ⚠️  Parse error: {e}")
    return items

def _get_text(el, tag, ns={}):
    found = el.find(tag, ns)
    if found is not None and found.text:
        return found.text.strip()
    return None

def parse_reddit(content, source):
    items = []
    try:
        data = json.loads(content)
        posts = data.get("data", {}).get("children", [])
        for post in posts[:MAX_ITEMS_PER_SOURCE]:
            d = post.get("data", {})
            if d.get("stickied") or d.get("is_self") is False and not d.get("url"):
                continue
            title = d.get("title", "")
            url = d.get("url", "") or f"https://reddit.com{d.get('permalink', '')}"
            selftext = d.get("selftext", "")[:400]
            score = d.get("score", 0)

            item_id = hashlib.md5(url.encode()).hexdigest()[:12]
            items.append({
                "id": item_id,
                "title": title,
                "url": url,
                "description": selftext,
                "source": source["id"],
                "sourceName": source["name"],
                "category": source["category"],
                "publishedAt": "",
                "summary_vi": "",
                "summary_en": "",
                "score": score,
            })
    except Exception as e:
        print(f"  ⚠️  Reddit parse error: {e}")
    return items

# ── Gemini API ──────────────────────────────────────────────────────────────
def gemini_summarize(title, description):
    """Tóm tắt song ngữ (Anh + Việt) + chấm điểm bằng Gemini"""
    fallback = (description[:150] + "...") if description else ""

    if not GEMINI_API_KEY:
        return fallback, fallback, 5

    prompt = (
        "You are a bilingual tech news summarizer.\n\n"
        f"Title: {title}\nContent: {description[:600]}\n\n"
        "Reply ONLY with this exact JSON (no extra text, no markdown):\n"
        "{\n"
        '  "summary_en": "1-2 sentence English summary, concise and informative",\n'
        '  "summary_vi": "Tóm tắt 1-2 câu tiếng Việt, súc tích và dễ hiểu",\n'
        '  "score": <integer 1-10 rating importance/interest>\n'
        "}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300}
    }).encode()

    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            text_clean = re.sub(r"```json|```", "", text).strip()
            parsed = json.loads(text_clean)
            return (
                parsed.get("summary_vi", fallback),
                parsed.get("summary_en", fallback),
                int(parsed.get("score", 5)),
            )
    except Exception as e:
        print(f"  \u26a0\ufe0f  Gemini error: {e}")
        return fallback, fallback, 5

# ── Main ────────────────────────────────────────────────────────────────────
def main():
    print(f"\n🗞️  NewsDigest Fetcher — {TODAY}")
    print("=" * 50)

    # Load existing data nếu có (tránh duplicate)
    existing = {}
    if OUTPUT_FILE.exists():
        try:
            old = json.loads(OUTPUT_FILE.read_text())
            existing = {item["id"]: item for item in old.get("items", [])}
            print(f"📦 Đã có {len(existing)} tin từ lần chạy trước\n")
        except:
            pass

    all_items = []

    for source in SOURCES:
        print(f"📡 {source['name']} [{source['category']}]...")
        is_reddit = source.get("type") == "reddit"
        content = fetch_url(source["url"], is_reddit=is_reddit)

        if not content:
            continue

        if is_reddit:
            items = parse_reddit(content, source)
        else:
            items = parse_rss(content, source)

        print(f"   → {len(items)} tin")

        # Summarize các tin chưa có
        new_count = 0
        for item in items:
            if item["id"] in existing:
                # Reuse summary cũ
                old_item = existing[item["id"]]
                item["summary_vi"] = old_item.get("summary_vi", "")
                item["summary_en"] = old_item.get("summary_en", "")
                item["score"] = old_item.get("score", 5)
            else:
                # Gọi Gemini
                if GEMINI_API_KEY and (item["description"] or item["title"]):
                    item["summary_vi"], item["summary_en"], item["score"] = gemini_summarize(item["title"], item["description"])
                    time.sleep(GEMINI_DELAY)
                    new_count += 1
                else:
                    item["summary_vi"] = item["description"][:150] if item["description"] else ""
                    item["summary_en"] = item["description"][:150] if item["description"] else ""
                    item["score"] = 5

            all_items.append(item)

        if new_count > 0:
            print(f"   ✨ Đã tóm tắt {new_count} tin mới")

    # Dedup theo ID
    seen = set()
    unique_items = []
    for item in all_items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique_items.append(item)

    # Sort theo score giảm dần
    unique_items.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Lấy categories
    categories = list(dict.fromkeys(s["category"] for s in SOURCES))

    output = {
        "date": TODAY,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "totalItems": len(unique_items),
        "categories": categories,
        "sources": [{"id": s["id"], "name": s["name"], "category": s["category"]} for s in SOURCES],
        "items": unique_items,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n✅ Đã lưu {len(unique_items)} tin → {OUTPUT_FILE}")

    # Tạo index.json (danh sách ngày có data)
    index_file = OUTPUT_DIR / "index.json"
    existing_dates = []
    if index_file.exists():
        try:
            existing_dates = json.loads(index_file.read_text())
        except:
            pass
    if TODAY not in existing_dates:
        existing_dates.insert(0, TODAY)
    existing_dates = existing_dates[:60]  # giữ 60 ngày gần nhất
    index_file.write_text(json.dumps(existing_dates, ensure_ascii=False, indent=2))
    print(f"📅 Updated index.json ({len(existing_dates)} ngày)")

if __name__ == "__main__":
    main()
