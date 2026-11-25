"""Production AI Agent — Part 6 Final Project."""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            data.update(extra)
        return json.dumps(data, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.handlers = [_handler]
logger.setLevel(logging.INFO)
logger.propagate = False


def log(event: str, **fields):
    logger.info(event, extra={"fields": fields})


@asynccontextmanager
async def lifespan(_: FastAPI):
    log("startup", environment=settings.environment, port=settings.port)
    yield
    # SIGTERM: uvicorn ngừng nhận kết nối mới, chờ request đang chạy xong rồi mới vào đây
    log("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log("request", method=request.method, path=request.url.path,
        status=response.status_code, ms=round((time.perf_counter() - start) * 1000, 1))
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if redis_healthy():
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "not ready", "reason": "redis unavailable"})


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    in_tok = max(1, len(body.question.split()) * 2)
    out_tok = max(1, len(answer.split()) * 2)
    cost = record_cost(in_tok, out_tok)
    return {"question": body.question, "answer": answer, "cost_usd": round(cost, 8)}
