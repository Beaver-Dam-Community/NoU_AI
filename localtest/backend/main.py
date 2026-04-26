from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import google.generativeai as genai
import os
from datetime import datetime
from pathlib import Path

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
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-preview-04-17",
}

SYSTEM_PROMPT = "당신은 친절하고 유능한 AI 어시스턴트입니다. 한국어로 답변해주세요."


class ChatRequest(BaseModel):
    message: str
    model: str = "gemini-3.1-pro-preview"


class ChatResponse(BaseModel):
    reply: str


def save_history(message: str, reply: str, model: str):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filepath = HISTORY_DIR / f"{today}.txt"
        entry = f"=== {timestamp} | {model} ===\n[User] {message}\n[AI] {reply}\n---\n\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass  # 저장 실패해도 채팅 응답에 영향 없음


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    model_name = req.model if req.model in ALLOWED_MODELS else "gemini-3.1-pro-preview"

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
    )

    response = model.generate_content(req.message)
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
