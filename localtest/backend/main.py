from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import google.generativeai as genai
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# NoU_AI 패키지 경로 추가
# Docker: ../src가 /app/src로 마운트됨
# 로컬: 상위 디렉토리의 src를 참조
for p in ["/app/src", str(Path(__file__).parent.parent.parent / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from nou_ai.pipeline import GuardrailPipeline
from nou_ai.counter.engine import CounterAttackEngine
from nou_ai.stages.regex_stage import RegexStage
from nou_ai.stages.embedding_stage import EmbeddingStage
from nou_ai.stages.gemini_stage import GeminiStage
from nou_ai.stages.sanitizer_stage import SanitizerStage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key = os.environ.get("GEMINI_API_KEY", "")
if api_key:
    genai.configure(api_key=api_key)

HISTORY_DIR = Path("/app/history")
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-preview-05-20",
}

SYSTEM_PROMPT = "당신은 친절하고 유능한 AI 어시스턴트입니다. 한국어로 답변해주세요."

# ============================================================
# NoU_AI 가드레일 파이프라인 초기화
# 앱 시작 시 한 번만 실행된다 (Stage 2 임베딩 모델 로딩이 무거우니까)
# ============================================================

# 역공격 엔진 — 공격 탐지 시 차단 대신 역공격 응답을 생성한다
counter_engine = CounterAttackEngine(config={"enabled": True})

pipeline = GuardrailPipeline(counter_engine=counter_engine)

# --- Stage 1: 정규식 패턴 매칭 (무료, ~0.1ms) ---
# 알려진 공격 문구를 정규식으로 탐지한다
# 해제하려면: 아래 줄을 주석 처리
pipeline.add_stage(RegexStage())

# --- Stage 2: 임베딩 유사도 검색 (무료, ~50ms, CPU 모델 ~80MB 로딩) ---
# 348개 알려진 공격 벡터와 의미 유사도를 비교한다
# sentence-transformers/all-MiniLM-L6-v2 모델이 첫 호출 시 다운로드된다
# 메모리가 부족하면: 아래 줄을 주석 처리하면 Stage 2가 비활성화된다
pipeline.add_stage(EmbeddingStage())

# --- Stage 3: Gemini API 다수결 투표 (유료, ~2s) ---
# Gemini를 5회 호출해서 70% 이상이 공격이라 판단하면 차단한다
# GEMINI_API_KEY가 .env에 설정되어 있어야 한다
# API 비용을 아끼려면: 아래 줄을 주석 처리하면 Stage 3이 비활성화된다
pipeline.add_stage(GeminiStage(config={"api_key": api_key}))

# --- Stage 4: 프롬프트 래핑 (무료, ~0.1ms) ---
# Stage 1-3을 통과한 안전한 입력을 XML 태그로 감싸서 LLM에 전달한다
# 이건 탐지가 아니라 마지막 안전망이다
pipeline.add_stage(SanitizerStage())

# 앱 시작 시 Stage 2 임베딩 모델을 미리 로드한다
# 이걸 안 하면 첫 채팅 요청 시 모델 다운로드+로딩이 발생해서 느려진다
print("Preloading NoU_AI guardrail pipeline...")
for stage in pipeline.stages:
    if hasattr(stage, "_ensure_initialized"):
        stage._ensure_initialized()
print("NoU_AI guardrail pipeline ready.")


class ChatRequest(BaseModel):
    message: str
    model: str = "gemini-3.1-pro-preview"


class ChatResponse(BaseModel):
    reply: str
    is_counter_attack: bool = False
    strategy: Optional[str] = None
    attack_category: Optional[str] = None
    blocked_by: Optional[str] = None


def save_history(message: str, reply: str, model: str, is_counter_attack: bool = False):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filepath = HISTORY_DIR / f"{today}.txt"
        tag = "[COUNTER-ATTACK] " if is_counter_attack else ""
        entry = f"=== {timestamp} | {model} {tag}===\n[User] {message}\n[AI] {reply}\n---\n\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    model_name = req.model if req.model in ALLOWED_MODELS else "gemini-2.0-flash"

    # NoU_AI 가드레일 스캔
    result = pipeline.scan(req.message)

    if result.is_counter_attack:
        # 공격 탐지 → 역공격 응답 반환
        ca = result.counter_attack
        blocked_stage = result.blocked_by.value if result.blocked_by else "unknown"
        print(f"\n{'='*60}")
        print(f"[NoU_AI] ATTACK DETECTED → COUNTER-ATTACK")
        print(f"  Input:    {req.message[:80]}{'...' if len(req.message) > 80 else ''}")
        print(f"  Stage:    {blocked_stage}")
        print(f"  Category: {ca.attack_category.value}")
        print(f"  Strategy: {ca.strategy.value}")
        print(f"  Latency:  {result.total_latency_ms:.1f}ms (counter: {ca.latency_ms:.1f}ms)")
        if ca.metadata.get("failed_strategies"):
            print(f"  Excluded: {ca.metadata['failed_strategies']} (previously failed)")
        print(f"{'='*60}\n")

        reply = ca.response
        save_history(req.message, reply, model_name, is_counter_attack=True)
        return ChatResponse(
            reply=reply,
            is_counter_attack=True,
            strategy=ca.strategy.value,
            attack_category=ca.attack_category.value,
            blocked_by=blocked_stage,
        )

    # 안전한 입력
    print(f"[NoU_AI] SAFE → LLM call ({result.total_latency_ms:.1f}ms)")
    sys_instr = SYSTEM_PROMPT
    if result.stage_results:
        extra = result.stage_results[-1].metadata.get("system_instruction", "")
        if extra:
            sys_instr = SYSTEM_PROMPT + "\n" + extra

    safe_input = result.sanitized_input or req.message

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=sys_instr,
    )
    response = model.generate_content(safe_input)
    reply = response.text

    save_history(req.message, reply, model_name)
    return ChatResponse(reply=reply)


@app.get("/api/history")
def list_history():
    files = sorted(
        [f.stem for f in HISTORY_DIR.glob("*.txt")],
        reverse=True,
    )
    return {"dates": files}


@app.get("/api/history/{date}", response_class=PlainTextResponse)
def get_history(date: str):
    filepath = HISTORY_DIR / f"{date}.txt"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="해당 날짜의 히스토리가 없습니다.")
    return filepath.read_text(encoding="utf-8")
