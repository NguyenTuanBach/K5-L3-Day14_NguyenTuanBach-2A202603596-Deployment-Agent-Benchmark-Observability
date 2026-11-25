# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Tuấn Bách — **MSSV:** 2A202603596
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11, Python 3.12, chạy agent develop trực tiếp (không Docker) trên localhost

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mock LLM mất ~150–200 ms; 500 ms cho dư địa gấp ~2,5 lần mà người dùng vẫn thấy nhanh |
| Error rate `/ask` | < 2 % | Cho phép lỗi lẻ tẻ (mock có tỉ lệ lỗi ngẫu nhiên) nhưng chặn lỗi hàng loạt |
| Accuracy trên golden dataset | ≥ 100 % (gate cuối), ≥ 80 % (gate mặc định) | Bộ 23 câu nhỏ, mỗi câu sai là một lỗ hổng kiến thức đã biết nên sửa hết |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`, 300 request mỗi mức)

### 2.1 Concurrency vs latency (agent v2, `MOCK_SLOW_RATE=0.03`)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3,94 | 203,3 | 236,5 | 1709,5 | 0,33 % | PASS |
| 10 | 41,95 | 190,5 | 274,2 | 1671,0 | 1,00 % | PASS |
| 50 | 95,12 | 199,7 | 521,2 | 1743,3 | 1,67 % | FAIL (p95 > 500) |
| 100 | 65,84 | 564,0 | 3553,0 | 3933,3 | 0,67 % | FAIL (p95 > 500) |

Nguồn: `reports/load_v2_c1.json`, `c10`, `c50`, `c100`. Mọi lỗi là HTTP 503 do mock LLM chủ ý sinh lỗi.

**Nhận xét:** RPS tăng gần tuyến tính từ 1 lên 10 (3,94 → 41,95, tức ×10,6) vì mỗi request chỉ chờ I/O. Lên 50 vẫn tăng (95,12) nhưng p95 đã vượt SLO. Ở 100 RPS **giảm** (65,84) và p95 vọt lên 3,5 s: một process uvicorn đã bão hòa, request xếp hàng. Trần của một instance nằm quanh 50 request song song với SLO này. Cần scale ngang hoặc thêm worker.

### 2.2 Tail latency (concurrency 20, 300 request)

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 203,6 | 441,4 | 475,4 |
| 0.03 (mặc định) | 241,9 | 459,1 | 1677,0 |
| 0.1 | 360,2 | 1688,5 | 1726,8 |

Nguồn: `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`.

**Nhận xét:** p99 nhạy nhất với request chậm hiếm (0 → 0,03: avg chỉ tăng 19 % nhưng p99 tăng ×3,5). Khi tỉ lệ chậm lên 10 %, p95 cũng vọt (1688 ms) và vi phạm SLO. Average che giấu đuôi: avg 360 ms trông ổn trong khi cứ 10 người thì 1 người chờ gần 1,7 s, nên SLO đặt theo p95/p99.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`, 23 câu)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4,3 % (1/23) | 91,3 % (21/23) | 100 % (23/23) |
| Avg tokens / câu | 57,0 | 109,0 | 113,7 |
| Tổng cost (USD) | 0,000402 | 0,000760 | 0,000791 |
| Cost / câu đúng (USD) | 0,000402 | 0,0000362 | 0,0000344 |
| Quality gate | FAIL (gate 0,8) | PASS (gate 0,8) | PASS (gate 1,0, 0 regression) |

Nguồn: `reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`.

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm mục `["jwt", "json web token"]` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`, nội dung nêu JWT là token có chữ ký và hết hạn, khác API key tĩnh |
| scaling-03 | cpu, memory, custom metrics | Thêm mục `["hpa", "kubernetes", "autoscal"]` nói HPA scale theo CPU, memory và custom metrics |

**Trade-off v1 / v2:** v2 dùng gấp ~1,9 lần token (109 so với 57) và tổng cost gần gấp đôi, nhưng accuracy từ 4,3 % lên 91,3 %. Tính theo **cost / câu đúng** v2 rẻ hơn v1 hơn 10 lần (0,0000362 so với 0,000402 USD), vì v1 gần như không có câu đúng nên mỗi câu đúng tốn rất nhiều. Latency p50 tăng nhẹ (173,7 → 205,8 ms) do thêm bước retrieval. Các số p95 của eval (1508 ms v1, 1700 ms v2) chỉ do 1 request chậm trong mẫu 23 câu, không dùng để kết luận latency (xem mục 2).

---

## 4. Observability stack (production)

Stack Docker Compose `-p k5-day14-observability`: agent x2, Nginx, Prometheus, Grafana, Jaeger, Locust (30 → 10 user nền). Grafana chạy ở cổng **3001** (cổng 3000 trên máy đang dùng cho dự án khác, đổi bằng file override ngoài repo, không sửa `docker-compose.yml`).

### 4.1 Screenshot

Ảnh đã lưu trong `screenshots/`:

- [x] `grafana-dashboard.png` — http://localhost:3001
- [x] `jaeger-slow-trace.png` — trace `4f192364a7b3a06cb259666210b30a0f`
- [x] `jaeger-error-trace.png` — trace `7135d8c69276cc4e49a12526fc2482df`
- [x] `prometheus-alert-firing.png` — http://localhost:9090/alerts

### 4.2 Thí nghiệm "phá hệ thống" (2 instance, 10 user Locust)

Thời gian đo bằng script poll `/api/v1/alerts` mỗi 5 giây, tính từ lúc chạy `docker compose up -d` áp dụng thay đổi.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (pending sau 31 s) | 87 s | Error rate; LLM calls theo kết quả |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (pending sau 20 s) | 144 s | Latency /ask p50/p95/p99 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (pending sau 51 s) | 170 s | Cost burn rate (USD/giờ); LLM latency p95 theo model |
| D | `docker pause` agent-1 | `AgentInstanceDown` (pending sau 10 s) | 41 s | Instances up |
| E | `AGENT_VERSION=v1` | Không có | — | Phiên bản đang chạy; Retrieval hit ratio |

Ghi chú đo:
- Tên panel lấy từ `agent-overview.json`; chưa đối chiếu bằng ảnh chụp.
- Ở C có thêm `AgentInstanceDown` pending trong 5 s đầu do container được tạo lại để áp dụng `.env` (không lên firing).
- D: sau khi pause, `AgentHighLatencyP95` còn lên pending sau 82 s do request dồn về instance còn lại.
- Ở 30 user, chi phí nền đã ~$2,3/giờ, vượt ngưỡng $2 của `LLMCostBurnRateHigh`, nên giảm Locust xuống 10 user để C phân biệt được.
- E: Prometheus báo `agent_info{version="v1"}` trên 2 instance, không alert nào firing.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Chạy eval trên golden dataset định kỳ hoặc trong CI trước mỗi lần deploy (v1 chỉ đúng 4,3 % so với v2 91,3 %, xem mục 3) và đặt quality gate. Thêm metric chất lượng online như retrieval hit ratio, tỉ lệ người dùng đánh giá xấu, và alert khi phiên bản đang chạy khác phiên bản kỳ vọng (`agent_info`).

### 4.3 Debug bằng trace

Trace chậm nhất trong 300 trace gần nhất (`MOCK_SLOW_RATE=0.1`):

- `trace_id`: `4f192364a7b3a06cb259666210b30a0f`
- Tổng thời gian: 1755,3 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1683,4 ms, 95,9 %); `agent.retrieve_context` chỉ 21,4 ms
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T14:05:44.097527+00:00", "level": "INFO", "service": "observable-agent", "instance": "44172da802f3", "event": "llm_call", "trace_id": "4f192364a7b3a06cb259666210b30a0f", "span_id": "286b16ac02a734d6", "request_id": "9c111350faf2", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 37, "output_tokens": 20, "cost_usd": 1.8e-05, "llm_ms": 1683.5}
{"ts": "2026-11-25T14:05:44.097879+00:00", "level": "INFO", "service": "observable-agent", "instance": "44172da802f3", "event": "http_request", "trace_id": "4f192364a7b3a06cb259666210b30a0f", "span_id": "286b16ac02a734d6", "request_id": "9c111350faf2", "method": "POST", "route": "/ask", "status": 200, "ms": 1754.8}
```

Trace lỗi (`MOCK_ERROR_RATE=0.05`): `7135d8c69276cc4e49a12526fc2482df`, 117,2 ms. Span `chat mock-llm-small` (98,1 ms) và `agent.run` có status lỗi và event `exception`; `POST /ask` trả 503.

```json
{"ts": "2026-11-25T14:06:15.790745+00:00", "level": "INFO", "service": "observable-agent", "instance": "0051b823e35f", "event": "llm_error", "trace_id": "7135d8c69276cc4e49a12526fc2482df", "span_id": "1a098f2b8f1b42b1", "request_id": "e10506f09487", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
{"ts": "2026-11-25T14:06:15.791000+00:00", "level": "INFO", "service": "observable-agent", "instance": "0051b823e35f", "event": "http_request", "trace_id": "7135d8c69276cc4e49a12526fc2482df", "span_id": "1a098f2b8f1b42b1", "request_id": "e10506f09487", "method": "POST", "route": "/ask", "status": 503, "ms": 116.8}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS (/ask) | p50 (ms) | p95 (ms) | p99 (ms) | Failures (/ask) |
|---|---|---|---|---|---|
| 1 | 59,86 | 190 | 230 | 1700 | 84 / 7155 (1,17 %) |
| 3 | 59,97 | 190 | 220 | 1700 | 85 / 7167 (1,19 %) |

Nguồn: `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv` (dòng `/ask`). Lần chạy scale_3 cuối cùng sau khi xác nhận Prometheus thấy 3 target `up` và Nginx chia đều 3 `X-Served-By`.

**Giải thích kết quả:** Scale lên 3 instance không đổi RPS, p50, p95, p99 hay tỉ lệ lỗi. Có hai nguyên nhân. (1) Tải do Locust quyết định: 100 user, mỗi user chờ ngẫu nhiên 0,5–2 s giữa các request (`between(0.5, 2)`) nên tải tối đa chỉ ~65 RPS, thấp hơn trần của một instance (load test local ở mục 2.1 vẫn đạt 95 RPS ở concurrency 50). (2) p99 = 1700 ms đến từ ~3 % request LLM chậm (`MOCK_SLOW_RATE`) và lỗi ~1 % là upstream mock, những thứ thêm instance không sửa được. Nút thắt nằm ở LLM upstream (span `chat ...` chiếm 96 % thời gian trace), không phải ở số instance agent. Muốn thấy lợi ích của scale cần tăng tải (nhiều user hoặc bỏ wait_time) cho tới khi một instance bão hòa.

---

## 6. Kết luận

1. Đặt SLO theo p95/p99, không theo average: ở `MOCK_SLOW_RATE=0.1` avg 360 ms trông ổn nhưng p95 1688 ms.
2. Throughput của một instance có trần: RPS giảm ở concurrency 100 và p95 vượt SLO từ concurrency 50.
3. So hai phiên bản bằng cost / câu đúng chứ không bằng cost / câu: v2 đắt hơn v1 theo từng câu nhưng rẻ hơn hơn 10 lần theo từng câu đúng.
4. Metric hạ tầng không bắt được lỗi chất lượng (thí nghiệm E) và scale ngang không sửa nút thắt ở upstream (mục 5): cần eval và trace song song với dashboard.

Sẽ thêm nếu đưa lên production thật: alert từ phía Nginx hoặc synthetic check (lỗi 504 không hiện ở metric agent), metric chất lượng online (tỉ lệ feedback xấu), và alert theo ngân sách thật thay vì ngưỡng $2/giờ cố định.
