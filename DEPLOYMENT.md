# Deployment Information

> Đã deploy lên Railway. `/health` trả `{"status":"ok"}`. Còn lại: chụp 3 ảnh trong `screenshots/`.

## Public URL
https://k5-l3-day14nguyentuanbach-2a202603596-deploymen-production.up.railway.app

## Platform
Railway (Root Directory `/06-lab-complete`, cấu hình trong `06-lab-complete/railway.toml`).

## Test Commands

```bash
BASE=https://k5-l3-day14nguyentuanbach-2a202603596-deploymen-production.up.railway.app
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200 (cần REDIS_URL trỏ tới Redis đang chạy)
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

## Environment Variables Set
- `PORT` (do nền tảng cấp)
- `REDIS_URL` (trỏ tới Redis tạo trên nền tảng)
- `AGENT_API_KEY` (secret, không ghi vào repo)
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`, `MONTHLY_BUDGET_USD=30.0`

## Screenshots
- `screenshots/dashboard.png` — Deployment dashboard
- `screenshots/running.png` — Service đang chạy
- `screenshots/test.png` — Kết quả 4 lệnh curl
