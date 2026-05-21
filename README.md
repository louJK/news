# 🗞️ NewsDigest — Tin tức AI & Tech (Tiếng Việt)

Tổng hợp tin từ 17+ nguồn (Hacker News, Reddit, TechCrunch, OpenAI, HuggingFace...), tóm tắt bằng Gemini AI, hiển thị bằng tiếng Việt. Tự động cập nhật mỗi 3 giờ.

## Demo

→ Deploy xong sẽ có dạng: `https://your-project.pages.dev`

---

## Cách deploy (15 phút)

### Bước 1 — Tạo GitHub repo

```bash
git clone https://github.com/YOUR_USERNAME/newsdigest
cd newsdigest
```

Hoặc fork repo này rồi đổi tên.

### Bước 2 — Lấy Gemini API Key (miễn phí)

1. Vào https://aistudio.google.com/app/apikey
2. Click **Create API Key**
3. Copy key lại

### Bước 3 — Thêm Secret vào GitHub

1. Vào repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `GEMINI_API_KEY`
4. Value: dán key vào
5. **Add secret**

### Bước 4 — Chạy lần đầu để có data

1. Vào **Actions** tab trong GitHub repo
2. Click **Fetch News** → **Run workflow** → **Run workflow**
3. Chờ ~3-5 phút để chạy xong
4. Kiểm tra thư mục `public/data/` đã có file JSON chưa

### Bước 5 — Deploy lên Cloudflare Pages

1. Vào https://pages.cloudflare.com → **Create a project**
2. **Connect to Git** → chọn repo GitHub của bạn
3. Cấu hình build:
   - **Framework preset**: None
   - **Build command**: _(để trống)_
   - **Build output directory**: `public`
4. **Save and Deploy**

Sau đó, mỗi khi GitHub Actions push data mới, Cloudflare Pages sẽ tự build lại.

---

## Cấu trúc project

```
newsdigest/
├── .github/workflows/
│   └── fetch-news.yml      # Cron job mỗi 3h
├── public/
│   ├── index.html          # Frontend SPA
│   └── data/
│       ├── index.json      # Danh sách ngày có data
│       └── 2026-05-20.json # Data theo ngày
├── scripts/
│   └── fetch.py            # Fetcher + Gemini summarizer
└── README.md
```

---

## Thêm/bớt nguồn tin

Mở `scripts/fetch.py`, tìm phần `SOURCES = [...]` và thêm:

```python
# RSS feed
{"id": "my_blog", "name": "My Blog", "category": "Tech", "url": "https://example.com/feed"},

# Reddit
{"id": "r_vietnam", "name": "r/vietnam", "category": "Tech",
 "url": "https://www.reddit.com/r/vietnam/hot.json?limit=10", "type": "reddit"},
```

**Categories hiện có**: `AI`, `Tech`, `Dev`

---

## Chạy local để test

```bash
# Cài Python 3.11+
pip install urllib3  # đã dùng stdlib, không cần thêm gì

# Set API key
export GEMINI_API_KEY="your-key-here"

# Chạy fetcher
python scripts/fetch.py

# Mở frontend
# Dùng Live Server (VSCode) hoặc:
python -m http.server 8080 --directory public
# Mở http://localhost:8080
```

---

## Tự động hóa

GitHub Actions tự động:
- **Mỗi 3 giờ**: Fetch + summarize tin mới
- **Chỉ commit** khi có thay đổi thực sự
- **Reuse** summary cũ, chỉ gọi Gemini cho tin mới → tiết kiệm quota

Gemini free tier: **1500 requests/ngày** — đủ dùng thoải mái.
