# Comparison with Existing Tools

NoU_AI analyzed 3 representative open-source guardrail projects, combined their strengths, and added **counter-attack** capability. This document explains how NoU_AI differs from each project and why these design choices were made.

[Korean version (한국어)](comparison-kor.md)

---

## At a Glance

| | Guardrails AI | NeMo Guardrails | Purple Llama | NoU_AI |
|---|---|---|---|---|
| **By** | Guardrails AI Inc. | NVIDIA | Meta | Us |
| **Core purpose** | LLM output validation | Dialogue flow control | AI safety models | **Counter-attack defense** |
| **On attack detection** | Block | Block | Block | **Generate counter-attack response** |
| **Self-improvement** | X | X | X | **O (auto weight adjustment)** |
| **GPU required** | X | X | O (recommended) | X |
| **Custom language** | X | O (Colang) | X | X |
| **Cost structure** | LLM API cost | LLM API cost | Model hosting cost | Stage 1,2 free / Stage 3 paid |

---

## The key difference: "Block" vs "Counter-Attack"

Existing tools all **block** when they detect an attack. "Sorry, I cannot process that request." End of story.

The problem: AI red team agents immediately try different attacks when blocked. Blocking is defense only — it doesn't drain the attacker's resources (tokens, time, compute).

NoU_AI implements the **[Mantis paper](https://arxiv.org/abs/2410.20911)** approach, generating **counter-attack responses** instead of blocking. These responses cause the attacker's AI agent to:
- Waste massive tokens (Token Exhaustion — ref: [Prompt-Induced Over-Generation](https://arxiv.org/abs/2512.23779))
- Fall into infinite loops (Infinite Loop)
- Accept fake information as real (Fake Compliance, Context Poison)
- Derail to completely different objectives (Goal Hijack — Mantis paper inspiration)

---

## vs Guardrails AI — "Output validation vs Counter-attack defense"

**What Guardrails AI does well:** Auto-reasks LLM when JSON output is malformed. Specialized in output format and quality validation.

**Limitation:** No built-in prompt injection detection — relies on Hub plugins. Even when detected, only blocks.

**How NoU_AI differs:** Focuses on **input defense + counter-attack**. The two tools are complementary — use NoU_AI for input defense/counter-attack and Guardrails AI for output validation.

**What we took from Guardrails AI:**
- FAISS VectorDB pattern -> Stage 2 vector search (`src/nou_ai/embeddings/faiss_index.py`)
- Modular Validator plugin architecture -> BaseStage + add_stage() chaining
- PassResult/FailResult pattern -> StageResult data type

---

## vs NVIDIA NeMo Guardrails — "General framework vs Specialized counter-attack"

**What NeMo does well:** Define dialogue flows with Colang DSL. Embedding similarity search for intent matching. 5 types of rails for fine-grained LLM control.

**Limitation:** Must learn Colang DSL. Complex setup. Overkill for prompt injection defense alone. Only blocks.

**How NoU_AI differs:** Python only — no new language to learn. 3 lines to integrate. And counter-attacks instead of blocking.

**What we took from NeMo:**
- Embedding similarity search architecture -> Stage 2 (`src/nou_ai/stages/embedding_stage.py`)
- sentence-transformers/all-MiniLM-L6-v2 model
- YAML-based configuration -> config.yaml

**What we changed:**
- Annoy -> FAISS: Annoy can't add new vectors to existing index (requires full rebuild). FAISS supports real-time additions.

---

## vs Meta Purple Llama — "Dedicated models vs API-based counter-attack"

**What Purple Llama does well:** Prompt Guard achieves AUC 0.998. LlamaFirewall orchestrates multiple scanners.

**Limitation:** Must deploy models. GPU practically required. Only blocks.

**How NoU_AI differs:** No model deployment. No GPU. Counter-attacks instead of blocking. Also, Prompt Guard is open-source so attackers can study bypass methods, while NoU_AI's Stage 3 uses closed-source Gemini API.

**What we took from Purple Llama:**
- LlamaFirewall ScanResult/ScanDecision pattern -> StageResult/Decision (`src/nou_ai/types.py`)
- "BLOCK on any scanner" aggregation -> short-circuit pipeline (`src/nou_ai/pipeline.py`)
- CodeShield 2-layer scanning -> Stage 1->2->3 cost escalation
- Custom scanner registration -> BaseStage abstract class (`src/nou_ai/stages/base.py`)

---

## NoU_AI's unique designs

### 1. Counter-Attack Engine
**Ref**: [Mantis paper (arxiv 2410.20911)](https://arxiv.org/abs/2410.20911) — 95%+ effectiveness.

Not found in any other open-source guardrail. Selects from 7 strategies to trap the attacker's AI agent.

### 2. Self-Improvement Loop
Tracks attacker behavior to automatically evaluate counter-attack effectiveness. Failed strategies get lower weights, successful ones get higher. No other tool has this feedback loop.

### 3. Gemini Majority Voting (Stage 3)
Exploits LLM non-determinism. 6 calls with majority vote produces more stable judgments than single calls.

---

## When to use which tool?

| Situation | Recommended |
|-----------|------------|
| Validate LLM output matches JSON schema | Guardrails AI |
| Fine-grained dialogue flow control | NeMo Guardrails |
| Highest detection accuracy with GPU available | Purple Llama |
| Detect prompt injection and **counter-attack** | **NoU_AI** |
| Input counter-attack + output validation | NoU_AI + Guardrails AI |

---

## References

| Reference | What we took |
|-----------|-------------|
| [Mantis (arxiv 2410.20911)](https://arxiv.org/abs/2410.20911) | Counter-attack concept, Goal Hijack strategy |
| [Prompt-Induced Over-Generation (arxiv 2512.23779)](https://arxiv.org/abs/2512.23779) | Token Exhaustion strategy |
| [Defense by Leveraging Attack (arxiv 2411.00459)](https://arxiv.org/abs/2411.00459) | Reversing attack techniques for defense |
| Purple Llama LlamaFirewall | ScanResult pattern, short-circuit, 2-layer scanning |
| NeMo Guardrails | Embedding similarity search, all-MiniLM-L6-v2 |
| Guardrails AI | FAISS vector DB, modular plugin architecture |
| [Promptmap2](https://github.com/utkusen/promptmap) | 69 attack rules, attack category taxonomy |
