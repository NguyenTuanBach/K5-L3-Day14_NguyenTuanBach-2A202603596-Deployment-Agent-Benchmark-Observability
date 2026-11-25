# Day 14 Lab — Mission Answers

**Họ tên:** Nguyễn Tuấn Bách — **MSSV:** 2A202603596

> Trạng thái: Part 1, 2, 4, 5, 6, 7 đã chạy và điền số đo thật. Part 3 (deploy cloud) cần tài khoản nên chưa có URL.

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`
1. Hardcode secret: `OPENAI_API_KEY = "sk-..."` và `DATABASE_URL` có mật khẩu (dòng 17–18). Push lên GitHub là lộ.
2. In secret ra log: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` (dòng 34).
3. Dùng `print` thay vì logging có cấu trúc, không có level hay timestamp, khó lọc và gom log.
4. Cấu hình cứng trong code (`DEBUG = True`, `MAX_TOKENS = 500`), không đọc từ biến môi trường.
5. Không có `/health` nên platform không biết khi nào cần restart.
6. Port cố định 8000 và `host="localhost"` (dòng 49–52): Railway/Render cấp port qua `PORT` và cần bind `0.0.0.0`.
7. `reload=True` trong code chạy production, tốn tài nguyên và không an toàn.
8. Không có xử lý SIGTERM (graceful shutdown) và không có xác thực cho `/ask`.

### Exercise 1.2: Gọi bản develop
```
$ curl -X POST "http://localhost:8000/ask?question=Hello"
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}

$ curl -i -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 422 Unprocessable Entity     # bản develop nhận question qua query, không nhận JSON
$ curl -o /dev/null -w '%{http_code}' localhost:8000/health
404                                    # không có health check
```
Log của server in thẳng secret: `[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this`.

### Exercise 1.3: Bảng so sánh
| Feature | Develop | Production | Vì sao quan trọng |
|---|---|---|---|
| Config | Hardcode trong code | Đọc từ biến môi trường (`config.py`) | Cùng một image chạy ở mọi môi trường, secret không vào git |
| Health check | Không có | `/health`, `/ready` | Platform biết khi nào restart, khi nào ngừng route traffic |
| Logging | `print`, lộ secret | JSON có cấu trúc | Tìm kiếm và liên kết với trace, không lộ secret |
| Shutdown | Tắt đột ngột | Graceful (SIGTERM, hoàn tất request đang chạy) | Không mất request của người dùng khi deploy |
| Port/host | `localhost:8000` cố định | `0.0.0.0` + `PORT` | Cloud inject port qua env |

## Part 2: Docker

### Exercise 2.1: Dockerfile (`02-docker/develop/Dockerfile`)
1. Base image: `python:3.11` (bản đầy đủ, khoảng 1 GB).
2. Working directory: `/app`.
3. `COPY requirements.txt` trước `COPY app.py`: để Docker cache layer cài dependencies, đổi code không phải cài lại.
4. CMD chạy uvicorn cho `app:app`.

### Exercise 2.3: So sánh kích thước image
Đo bằng `docker image inspect` và `docker images` sau khi build từ gốc repo:
```
my-agent:develop   1.67GB  (1,667,777,073 bytes)
my-agent:advanced  240MB   (  239,815,030 bytes)
```
- Develop: 1667,8 MB — Production: 239,8 MB — Chênh lệch: giảm 85,6 %.
- Container develop chạy được: `curl -X POST "http://localhost:8000/ask?question=What%20is%20Docker"` trả `{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}`.
- Multi-stage nhỏ hơn vì stage builder (compiler, cache pip) bị bỏ lại, stage runtime chỉ copy dependencies đã cài; base `python:3.11-slim` thay cho `python:3.11` đầy đủ.

### Exercise 2.4: Stack Docker Compose + Nginx
Các service (`docker compose -p k5-day14-docker up -d --build`, đều healthy):
```
Client --:80--> nginx --> agent (8000, nội bộ) --> redis (6379, session/rate limit)
                                              \--> qdrant (6333, vector DB cho RAG)
```
Chỉ Nginx mở cổng ra ngoài (80, 443); agent, redis, qdrant nằm trong network `internal` và nói chuyện nhau bằng tên service. Agent chỉ start khi redis và qdrant healthy (`depends_on: condition: service_healthy`).
```
$ curl -i http://localhost/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":18.6,"version":"2.0.0","timestamp":"2026-11-25T09:57:47.510207"}
$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
HTTP/1.1 200 OK
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

## Part 3: Cloud Deployment

### Exercise 3.1/3.2
- URL: https://k5-l3-day14nguyentuanbach-2a202603596-deploymen-production.up.railway.app (Railway, xem `DEPLOYMENT.md`)
- Ảnh: `screenshots/dashboard.png`, `running.png`, `test.png`
- So sánh: `railway.toml` khai báo `builder = "DOCKERFILE"` và `healthcheckPath` ngay trong repo, Railway tự cấp domain và biến `PORT`. `render.yaml` là Blueprint khai báo nhiều service cùng lúc, secret dùng `generateValue: true` hoặc `sync: false`, Redis phải tự khai báo.

### Exercise 3.3: Cloud Run
`cloudbuild.yaml` build image, push lên registry, rồi deploy lên Cloud Run theo `service.yaml` (autoscale, biến môi trường, health probe). Có thể gắn trigger theo push để thành CI/CD.

## Part 4: API Security

### Exercise 4.1–4.3
**4.1 API key (`04-api-gateway/develop`, `AGENT_API_KEY=secret-key-123`):**
```
$ curl -i -X POST localhost:8010/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized   {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
$ curl -i ... -H "X-API-Key: wrong"
HTTP/1.1 403 Forbidden      {"detail":"Invalid API key."}
$ curl -i ... -H "X-API-Key: secret-key-123"
HTTP/1.1 200 OK             {"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```
Key được kiểm tra ở dependency `verify_api_key` (`develop/app.py`); sai key trả 403, thiếu key trả 401. Rotate key bằng cách đổi biến môi trường `AGENT_API_KEY` và restart. (Chạy ở cổng 8010 vì cổng 8000 bị tiến trình cũ chiếm; bản develop Part 4 nhận JSON.)

**4.2 JWT (`04-api-gateway/production`):**
```
$ curl -i -X POST localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
HTTP/1.1 200 OK
{"access_token":"<đã che>","token_type":"bearer","expires_in_minutes":60,...}
$ curl -i -X POST localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 401 Unauthorized
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

**4.3 Rate limiting:** thuật toán sliding window counter (deque timestamp mỗi user, in-memory), user 10 req/phút, admin 100 req/phút (`rate_limiter_admin`), admin được bypass bằng limiter riêng theo role. Vòng lặp 15 request với token `student`:
```
1-10:  HTTP/1.1 200 OK   (requests_remaining giảm 9 -> 0)
11-15: HTTP/1.1 429 Too Many Requests
       {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":56}}
```

### Exercise 4.4: Cách làm cost guard
Trong `06-lab-complete/app/cost_guard.py`: sau mỗi request, `record_cost` tính chi phí theo token (`input/1000 × giá input + output/1000 × giá output`) rồi cộng dồn vào hai khóa Redis `cost:day:<YYYY-MM-DD>` và `cost:month:<YYYY-MM>` bằng `INCRBYFLOAT` (có TTL để tự dọn). Trước khi gọi LLM, `check_budget` đọc hai khóa này, nếu tổng ngày ≥ `DAILY_BUDGET_USD` hoặc tháng ≥ `MONTHLY_BUDGET_USD` thì trả **402**. Lưu trong Redis (không trong RAM) để mọi worker và instance dùng chung và state sống qua restart. Rate limit bảo vệ tốc độ, cost guard bảo vệ tiền; cần cả hai vì một client chậm vẫn có thể đốt hết ngân sách bằng câu hỏi tốn token.

## Part 5: Scaling & Reliability

- Liveness (`/health`) chỉ cho biết process còn sống, luôn 200 kể cả khi Redis chết. Readiness (`/ready`) cho biết instance có phục vụ được không: 503 khi Redis mất, để load balancer ngừng route nhưng không restart.
- State trong RAM hỏng khi chạy nhiều instance vì request kế tiếp có thể đến instance khác. Giải pháp: giữ session, rate limit, cost trong Redis (đã làm ở Part 6).
- **Exercise 5.4** (`docker compose -p k5-day14-scaling up -d --build --scale agent=3`): 3 agent + redis + nginx đều healthy. 6 request tới `localhost:8080/chat` được chia đều; log có đủ `agent-1`, `agent-2`, `agent-3` (11 dòng mỗi instance).
- **Exercise 5.5** (`python test_stateless.py`): 5 request cùng một session đi qua 3 instance khác nhau (`instance-9e5535`, `instance-50cbcd`, `instance-73bd83`), sau đó history có đủ 10 message (`Session history preserved across all instances via Redis`). Script không tự tắt instance, chỉ chứng minh state nằm ở Redis chứ không ở RAM từng instance.

## Part 6: Output `check_production_ready.py`

Chạy đầy đủ (có Docker) trong WSL2 Ubuntu với Python 3.12 (`os.name == posix`), từ thư mục `06-lab-complete/`:

```
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Image đo được 238 MB (lượt chạy trên Windows).

## Part 7
Xem `BENCHMARK_REPORT.md`, `reports/` và `benchmark-results/`. Cả Bước 1 (load test, eval) và Bước 2 (stack observability, 5 thí nghiệm, scale 1 và 3 instance, trace) đã chạy; ảnh chụp màn hình phải chụp tay.

## AI log
Dùng Claude Code (Claude Sonnet 5.5) để: hoàn thiện các TODO trong `06-lab-complete/app/`, Dockerfile, compose, cấu hình deploy; chạy các bài Part 1, 2, 4, 5 và Part 7 (load test, eval, stack observability, thí nghiệm alert); sửa lỗi `PYTHONPATH` trong Dockerfile của stack Part 7; soạn các file báo cáo. Số liệu trong `BENCHMARK_REPORT.md` lấy từ file JSON/CSV trong `reports/` và `benchmark-results/` hoặc từ API Prometheus/Jaeger; không dùng số ước lượng.
