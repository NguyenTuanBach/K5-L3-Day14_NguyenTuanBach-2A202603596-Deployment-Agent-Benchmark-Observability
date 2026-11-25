# Deployment Information

> **CHƯA DEPLOY.** Cần tài khoản Railway/Render của bạn. Điền URL và key sau khi deploy, rồi chụp 3 ảnh trong `screenshots/`.

## Public URL
`https://<điền-sau-khi-deploy>` (Railway hoặc Render)

## Platform
Railway (`06-lab-complete/railway.toml`) hoặc Render (`06-lab-complete/render.yaml`). Cả hai đã viết sẵn và qua kiểm tra của `check_production_ready.py`.

## Test Commands

```bash
BASE=https://<url>
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
