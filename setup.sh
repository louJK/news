#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  NewsDigest — GitHub Repo Setup Script
#  Chạy: bash setup.sh
#  Yêu cầu: git, curl (có sẵn trên mọi máy Linux/Mac)
# ═══════════════════════════════════════════════════════════

set -e

# ── Màu sắc ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   NewsDigest — GitHub Auto Setup     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# ── Bước 1: GitHub Token ──────────────────────────────────
echo -e "${YELLOW}[1/5] GitHub Personal Access Token${NC}"
echo "    → Vào: https://github.com/settings/tokens/new"
echo "    → Tên token: newsdigest-setup"
echo "    → Chọn scope: ✅ repo (toàn bộ)"
echo "    → Click 'Generate token' → Copy"
echo ""
read -p "    Dán token vào đây: " GITHUB_TOKEN
echo ""

# ── Lấy username từ token ──
echo -e "${YELLOW}[2/5] Kiểm tra token & lấy username...${NC}"
GITHUB_USER=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/user | grep '"login"' | head -1 | \
    sed 's/.*"login": "\(.*\)".*/\1/')

if [ -z "$GITHUB_USER" ]; then
    echo -e "${RED}❌ Token không hợp lệ. Kiểm tra lại.${NC}"
    exit 1
fi
echo -e "    ✅ Đăng nhập thành công: ${GREEN}@${GITHUB_USER}${NC}"
echo ""

# ── Bước 2: Tên repo ──────────────────────────────────────
echo -e "${YELLOW}[3/5] Đặt tên repo${NC}"
read -p "    Tên repo [mặc định: newsdigest]: " REPO_NAME
REPO_NAME=${REPO_NAME:-newsdigest}
echo ""

# ── Bước 3: Tạo repo trên GitHub ─────────────────────────
echo -e "${YELLOW}[4/5] Tạo repo GitHub...${NC}"
RESPONSE=$(curl -s -o /tmp/gh_response.json -w "%{http_code}" \
    -X POST https://api.github.com/user/repos \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"$REPO_NAME\",
        \"description\": \"Tổng hợp tin AI & Tech hàng ngày, tóm tắt song ngữ Anh-Việt bằng Gemini AI\",
        \"private\": false,
        \"auto_init\": false
    }")

if [ "$RESPONSE" = "201" ]; then
    echo -e "    ✅ Repo tạo thành công: ${GREEN}https://github.com/${GITHUB_USER}/${REPO_NAME}${NC}"
elif [ "$RESPONSE" = "422" ]; then
    echo -e "    ⚠️  Repo đã tồn tại — tiếp tục push lên repo cũ"
else
    echo -e "    ${RED}❌ Lỗi HTTP $RESPONSE${NC}"
    cat /tmp/gh_response.json
    exit 1
fi
echo ""

# ── Bước 4: Push code ─────────────────────────────────────
echo -e "${YELLOW}[5/5] Push code lên GitHub...${NC}"

# Init git nếu chưa có
if [ ! -d ".git" ]; then
    git init
    echo "    ✅ git init"
fi

# Config git
git config user.email "setup@newsdigest.local" 2>/dev/null || true
git config user.name "NewsDigest Setup" 2>/dev/null || true

# Add remote (xóa cũ nếu có)
git remote remove origin 2>/dev/null || true
git remote add origin "https://${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"

# Stage và commit
git add -A
git diff --cached --quiet && echo "    ℹ️  Không có file mới" || {
    git commit -m "🚀 Initial setup: NewsDigest bilingual AI news aggregator"
    echo "    ✅ Committed"
}

# Push
git branch -M main
git push -u origin main --force
echo -e "    ✅ Push thành công!"
echo ""

# ── Bước 5: Thêm Gemini API Key secret ───────────────────
echo -e "${YELLOW}[+] Thêm GEMINI_API_KEY secret...${NC}"
echo "    → Lấy key miễn phí tại: https://aistudio.google.com/app/apikey"
echo ""
read -p "    Dán GEMINI_API_KEY (Enter để bỏ qua): " GEMINI_KEY

if [ -n "$GEMINI_KEY" ]; then
    # Lấy public key của repo để encrypt secret
    PK_RESPONSE=$(curl -s \
        -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/${GITHUB_USER}/${REPO_NAME}/actions/secrets/public-key")

    PK_ID=$(echo $PK_RESPONSE | grep '"key_id"' | sed 's/.*"key_id": "\(.*\)".*/\1/')

    if [ -n "$PK_ID" ]; then
        # Encrypt bằng Python (có sẵn trên mọi máy)
        ENCRYPTED=$(python3 - << PYEOF
import base64, sys
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.bindings._rust import openssl as rust_openssl

# Dùng libsodium qua PyNaCl nếu có
try:
    from nacl import encoding, public
    import json

    response = '''$PK_RESPONSE'''
    import re
    key_b64 = re.search(r'"key":\s*"([^"]+)"', response).group(1)
    pk = public.PublicKey(key_b64.encode(), encoding.Base64Encoder())
    box = public.SealedBox(pk)
    encrypted = box.encrypt("$GEMINI_KEY".encode())
    print(base64.b64encode(encrypted).decode())
except ImportError:
    print("NACL_NOT_AVAILABLE")
PYEOF
)

        if [ "$ENCRYPTED" = "NACL_NOT_AVAILABLE" ]; then
            echo -e "    ${YELLOW}⚠️  Thêm secret thủ công:${NC}"
            echo "    → https://github.com/${GITHUB_USER}/${REPO_NAME}/settings/secrets/actions/new"
            echo "    → Name: GEMINI_API_KEY"
            echo "    → Value: $GEMINI_KEY"
        else
            curl -s -X PUT \
                -H "Authorization: token $GITHUB_TOKEN" \
                -H "Content-Type: application/json" \
                "https://api.github.com/repos/${GITHUB_USER}/${REPO_NAME}/actions/secrets/GEMINI_API_KEY" \
                -d "{\"encrypted_value\":\"$ENCRYPTED\",\"key_id\":\"$PK_ID\"}" > /dev/null
            echo -e "    ✅ Secret GEMINI_API_KEY đã được thêm!"
        fi
    else
        echo -e "    ${YELLOW}⚠️  Thêm secret thủ công tại:${NC}"
        echo "    → https://github.com/${GITHUB_USER}/${REPO_NAME}/settings/secrets/actions/new"
    fi
else
    echo "    ⏭️  Bỏ qua — nhớ thêm thủ công sau"
fi

# ── Tổng kết ──────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ HOÀN THÀNH!                                      ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  📁 Repo:    https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo -e "${GREEN}║${NC}  ⚙️  Actions: https://github.com/${GITHUB_USER}/${REPO_NAME}/actions"
echo -e "${GREEN}║${NC}  🔑 Secrets: https://github.com/${GITHUB_USER}/${REPO_NAME}/settings/secrets/actions"
echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  BƯỚC TIẾP THEO:"
echo -e "${GREEN}║${NC}  1. Chạy workflow lần đầu để có data:"
echo -e "${GREEN}║${NC}     → Actions → Fetch News → Run workflow"
echo -e "${GREEN}║${NC}  2. Deploy lên Cloudflare Pages:"
echo -e "${GREEN}║${NC}     → https://pages.cloudflare.com"
echo -e "${GREEN}║${NC}     → Connect repo, Build output: public"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
