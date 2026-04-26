FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# pip 업그레이드 (해시 불일치 방지)
RUN pip install --upgrade pip

# PyTorch CPU-only 버전 먼저 설치 (~200MB, GPU 버전은 ~2GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 나머지 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
