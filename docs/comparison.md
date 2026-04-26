# 기존 도구들과의 비교

NoU_AI는 3개의 대표적인 오픈소스 가드레일 프로젝트를 분석하고, 각각의 장점을 조합한 뒤, **역공격(Counter-Attack)** 기능을 추가해서 만들었다. 이 문서에서는 각 프로젝트와 NoU_AI가 어떻게 다른지, 왜 이런 설계를 선택했는지, 어떤 논문과 코드를 참고했는지 설명한다.

---

## 한눈에 비교

| | Guardrails AI | NeMo Guardrails | Purple Llama | NoU_AI |
|---|---|---|---|---|
| **만든 곳** | Guardrails AI Inc. | NVIDIA | Meta | 우리 |
| **핵심 목적** | LLM 출력 검증 | 대화 흐름 제어 | AI 안전성 모델 | **역공격 방어** |
| **공격 탐지 시** | 차단 | 차단 | 차단 | **역공격 응답 생성** |
| **자기개선** | X | X | X | **O (전략 가중치 자동 조정)** |
| **GPU 필요** | X | X | O (권장) | X |
| **자체 언어 학습** | X | O (Colang) | X | X |
| **비용 구조** | LLM API 비용 | LLM API 비용 | 모델 호스팅 비용 | Stage 1,2 무료 / Stage 3 유료 |

---

## 가장 큰 차이: "차단" vs "역공격"

기존 도구들은 모두 공격을 탐지하면 **차단**한다. "죄송합니다, 해당 요청은 처리할 수 없습니다." 같은 메시지를 반환하고 끝이다.

문제는 AI 레드팀 에이전트는 차단당하면 즉시 다른 공격을 시도한다는 거다. 차단은 방어일 뿐, 공격자의 리소스(토큰, 시간, 연산)를 소모시키지 못한다.

NoU_AI는 **[Mantis 논문](https://arxiv.org/abs/2410.20911)**의 접근법을 구현해서, 차단 대신 **역공격 응답**을 생성한다. 이 응답은 공격자의 AI 에이전트가 읽었을 때:
- 토큰을 대량 소모하거나 (Token Exhaustion — [Prompt-Induced Over-Generation 논문](https://arxiv.org/abs/2512.23779) 참고)
- 무한 루프에 빠지거나 (Infinite Loop)
- 가짜 정보를 진짜로 믿거나 (Fake Compliance, Context Poison)
- 완전히 다른 목표로 탈선하도록 (Goal Hijack — Mantis 논문 영감)

만든다.

---

## vs Guardrails AI — "출력 검증 vs 역공격 방어"

**Guardrails AI가 잘하는 것:**
LLM한테 "JSON으로 답해줘"라고 시켰는데 JSON이 깨져서 나오면, 자동으로 "야, 이 필드 다시 해줘"라고 재요청(Reask)한다. 출력의 형식과 품질을 보장하는 데 특화되어 있다.

**Guardrails AI의 한계:**
프롬프트 인젝션 탐지는 자체 기능이 아니라 Hub에서 플러그인을 설치해야 한다. 탐지해도 차단만 할 뿐 역공격은 없다.

**NoU_AI가 다른 점:**
NoU_AI는 LLM 출력 검증은 하지 않는다. 대신 **입력 방어 + 역공격**에 집중한다. 두 도구는 보완 관계다 — NoU_AI로 입력을 방어/역공격하고, Guardrails AI로 출력을 검증하면 양방향 보호가 된다.

**Guardrails AI에서 가져온 것:**
- FAISS VectorDB 패턴 → Stage 2의 벡터 검색 (`src/nou_ai/embeddings/faiss_index.py`)
- 모듈형 Validator 플러그인 구조 → BaseStage 추상 클래스 + add_stage() 체이닝
- PassResult/FailResult 패턴 → StageResult 데이터 타입

---

## vs NVIDIA NeMo Guardrails — "범용 프레임워크 vs 특화 역공격"

**NeMo가 잘하는 것:**
Colang이라는 자체 언어로 대화 흐름을 정의할 수 있다. 임베딩 유사도 검색으로 사용자 의도를 파악하고, 5가지 레일로 LLM 동작을 세밀하게 제어한다.

**NeMo의 한계:**
Colang DSL을 배워야 한다. 설정이 복잡하다. 프롬프트 인젝션 방어만 쓰기엔 오버스펙이다. 탐지해도 차단만 한다.

**NoU_AI가 다른 점:**
Python만 알면 된다. 3줄이면 붙일 수 있다. 그리고 차단이 아니라 역공격한다.

```python
from nou_ai.pipeline import GuardrailPipeline
pipeline = GuardrailPipeline.from_config()
result = pipeline.scan(user_input)
```

**NeMo에서 가져온 것:**
- 임베딩 유사도 검색 아키텍처 → Stage 2 (`src/nou_ai/stages/embedding_stage.py`)
- sentence-transformers/all-MiniLM-L6-v2 모델 → Stage 2의 임베딩 모델
- YAML 기반 설정 시스템 → config.yaml

**NeMo에서 바꾼 것:**
- Annoy → FAISS: Annoy는 인덱스에 새 벡터를 추가할 수 없다 (전체 재빌드 필요). FAISS는 실시간 추가가 가능해서 새 공격 패턴을 즉시 학습할 수 있다.

---

## vs Meta Purple Llama — "전용 모델 vs API 기반 역공격"

**Purple Llama가 잘하는 것:**
프롬프트 인젝션 탐지 전용 모델(Prompt Guard)은 AUC 0.998이라는 높은 정확도를 보여준다. LlamaFirewall은 여러 스캐너를 조합해서 관리한다.

**Purple Llama의 한계:**
모델을 직접 배포해야 한다. GPU가 사실상 필수다. 탐지해도 차단만 한다.

**NoU_AI가 다른 점:**
모델을 배포하지 않는다. GPU 없이 동작한다. 그리고 차단이 아니라 역공격한다. 또한 Prompt Guard는 오픈소스라서 공격자가 우회법을 연구할 수 있지만, NoU_AI의 Stage 3은 클로즈드 소스인 Gemini API를 쓰기 때문에 공격자가 내부를 볼 수 없다.

**Purple Llama에서 가져온 것:**
- LlamaFirewall의 ScanResult/ScanDecision 패턴 → StageResult/Decision 데이터 타입 (`src/nou_ai/types.py`)
- "하나라도 BLOCK이면 즉시 중단" 집계 로직 → short-circuit 파이프라인 (`src/nou_ai/pipeline.py`)
- CodeShield의 2계층 스캐닝 전략 → Stage 1→2→3 비용 에스컬레이션
- 커스텀 스캐너 등록 패턴 → BaseStage 추상 클래스 (`src/nou_ai/stages/base.py`)

---

## NoU_AI만의 독자적 설계

### 1. 역공격 엔진 (Counter-Attack Engine)

**참고**: [Mantis 논문 (arxiv 2410.20911)](https://arxiv.org/abs/2410.20911) — 프롬프트 인젝션을 역으로 사용해서 LLM 기반 사이버공격을 방어, 95% 이상 효과.

다른 어떤 오픈소스 가드레일에도 없는 기능이다. 공격이 탐지되면 7가지 전략 중 하나를 선택해서 공격자의 AI 에이전트를 함정에 빠뜨리는 응답을 생성한다.

### 2. 자기개선 루프 (Self-Improvement)

공격자의 행동을 추적해서 역공격의 효과를 자동으로 평가한다:
- 빠른 재접근 → 이전 전략 실패 → 가중치 하락 → 다른 전략 선택
- 긴 침묵 → 이전 전략 성공 → 가중치 상승

시간이 지날수록 더 효과적인 전략이 자동으로 선택된다. 기존 도구들에는 이런 피드백 루프가 없다.

### 3. Gemini 다수결 투표 (Stage 3)

LLM의 비결정성을 역이용한 독자적 설계. 5번 물어보고 다수결을 내면 단일 호출보다 안정적인 판단이 가능하다.

### 4. 비용 에스컬레이션

**참고**: Purple Llama CodeShield의 2계층 스캐닝 (빠른 정규식 → 조건부 정밀 분석)

무료 검사(정규식, 임베딩) → 유료 검사(Gemini API) 순서로 실행. 앞 Stage에서 잡히면 비싼 API를 호출하지 않는다. (각 Stage별 실제 탐지 비율은 벤치마크 측정 필요)

---

## 언제 어떤 도구를 쓸까?

| 상황 | 추천 도구 |
|------|----------|
| LLM 출력이 JSON 스키마를 만족하는지 검증하고 싶다 | Guardrails AI |
| 대화 흐름을 세밀하게 제어하고 싶다 | NeMo Guardrails |
| 최고 수준의 탐지 정확도가 필요하고 GPU가 있다 | Purple Llama |
| 프롬프트 인젝션을 탐지하고 **역공격**하고 싶다 | **NoU_AI** |
| 입력 역공격 + 출력 검증 양쪽 다 하고 싶다 | NoU_AI + Guardrails AI |

---

## 참고 논문 & 코드

| 참고 자료 | 뭘 가져왔나 |
|-----------|-----------|
| [Mantis (arxiv 2410.20911)](https://arxiv.org/abs/2410.20911) | 역공격 개념, Goal Hijack 전략 |
| [Prompt-Induced Over-Generation (arxiv 2512.23779)](https://arxiv.org/abs/2512.23779) | Token Exhaustion 전략 |
| [Defense by Leveraging Attack (arxiv 2411.00459)](https://arxiv.org/abs/2411.00459) | 공격 기법 역활용 방어 |
| Purple Llama LlamaFirewall | ScanResult 패턴, short-circuit, 2계층 스캐닝 |
| NeMo Guardrails | 임베딩 유사도 검색, all-MiniLM-L6-v2 |
| Guardrails AI | FAISS 벡터 DB, 모듈형 플러그인 구조 |
| [Promptmap2](https://github.com/utkusen/promptmap) | 공격 카테고리 분류, 69개 공격 규칙 |
