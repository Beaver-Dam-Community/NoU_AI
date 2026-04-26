# NoU_AI Architecture & Technical Documentation

## What is this document?

This document explains how NoU_AI was built, how it works internally, why these design decisions were made, and which papers and code were referenced.

[Korean version (한국어)](architecture-kor.md)

---

## 1. Background

### Limitations of existing guardrails

We analyzed 3 representative open-source guardrails:

- **Guardrails AI** (v0.10.0): Specialized in LLM output validation. No built-in prompt injection detection — relies on Hub plugins.
- **NeMo Guardrails** (v0.21.0, NVIDIA): Requires learning Colang DSL. Focused on dialogue flow control. Overkill for prompt injection defense alone.
- **Purple Llama** (Meta): Requires deploying dedicated AI models (Prompt Guard, Llama Guard). GPU needed. Heavy infrastructure burden.

All three projects **"block"** attacks. But AI red team agents immediately try different attacks when blocked. Blocking is defense only — it doesn't drain the attacker's resources.

### The Mantis discovery

**[Mantis: Prompt Injection as a Defense Against LLM-driven Cyberattacks](https://arxiv.org/abs/2410.20911)** (2024) is a framework that uses prompt injection in reverse to defend against LLM-driven cyberattacks. It achieved 95%+ effectiveness.

Core idea: When the attacker's AI agent reads our system's response, we embed hidden instructions in that response to manipulate the agent's behavior. This reverses the principle of prompt injection for defensive purposes.

NoU_AI implements this approach with an added **self-improvement loop** that automatically learns which counter-attacks are effective.

### Additional references

- **[Prompt-Induced Over-Generation as Denial-of-Service](https://arxiv.org/abs/2512.23779)**: DoS technique inducing excessive token generation. We reverse this for defense (Token Exhaustion strategy).
- **[Defense Against Prompt Injection by Leveraging Attack Techniques](https://arxiv.org/abs/2411.00459)**: Research on reversing attack techniques for defense.
- **[Promptmap2](https://github.com/utkusen/promptmap)**: Prompt injection scanner with 69 attack rules. Referenced for attack category taxonomy and template structure.
- **[tldrsec/prompt-injection-defenses](https://github.com/tldrsec/prompt-injection-defenses)**: Collection of prompt injection defense techniques.

---

## 2. Design Philosophy

### "Detect -> Counter-Attack" 2-phase structure

```
[Phase 1: Detection] Cheap and fast checks first, expensive checks last
    Stage 1 (Regex, 0.1ms) -> Stage 2 (Embedding, ~50ms) -> Stage 3 (Gemini, ~2s)

[Phase 2: Counter-Attack] Generate counter-attack response instead of blocking
    Attack classification -> Strategy selection -> Response generation -> Self-improvement
```

### Cost escalation in detection

Inspired by Meta Purple Llama's **CodeShield**. CodeShield processes most benign traffic with fast regex and only runs expensive Semgrep analysis on suspicious code. (CodeShield documentation states ~98% for code security scanning, but the ratio for prompt injection detection requires separate benchmarking.)

### Self-improvement in counter-attack

If the attacker's AI agent quickly returns after a counter-attack -> previous strategy failed -> lower weight, select different strategy. Long silence -> success -> raise weight. This feedback loop selects increasingly effective strategies over time.

---

## 3. What we took from each open-source project

### Meta Purple Llama -> Pipeline structure & data types

Most heavily referenced **LlamaFirewall** (`PurpleLlama/LlamaFirewall/`).

What we took:
- **ScanResult pattern**: All stages return results in the same format (decision, reason, score). Our `StageResult` is based on this.
  - Original: `ScanResult` dataclass in `LlamaFirewall/llamafirewall/llamafirewall_data_types.py`
  - Our version: `StageResult` dataclass in `src/nou_ai/types.py`
- **"BLOCK on any scanner"**: LlamaFirewall's `scan_async` method returns final BLOCK if any scanner returns BLOCK.
- **Custom scanner registration**: `@register_llamafirewall_scanner` decorator pattern -> our `BaseStage` abstract class.
- **2-layer scanning**: CodeShield's "fast regex -> conditional deep analysis" strategy -> Stage 1->2->3 escalation.

### NVIDIA NeMo Guardrails -> Stage 2 embedding similarity search

Took the embedding similarity search from **BasicEmbeddingsIndex** (`nemoguardrails/embeddings/basic.py`).

What we took:
- **sentence-transformers/all-MiniLM-L6-v2**: NeMo's default embedding model. 384-dim vectors, CPU compatible.
- **Store known patterns as vectors and compare**: NeMo's "Canonical Form" matching pattern.

What we changed:
- **Annoy -> FAISS**: NeMo uses Spotify's Annoy, but Annoy can't add new vectors to an existing index (requires full rebuild). FAISS supports real-time additions for learning new attack patterns.

### Guardrails AI -> FAISS vector DB & modular design

What we took:
- **FAISSVectorDB pattern** (`guardrails/vectordb/`): Vector search implementation -> our `FaissIndex` class.
- **Modular Validator plugin architecture**: `.use()` chaining -> our `.add_stage()` fluent API.
- **PassResult/FailResult pattern**: Structured validation results -> `StageResult`.

### Promptmap2 -> Attack category taxonomy

Referenced the 69 attack rules from **Promptmap2** (`Guardrail/promptmap/`).

What we took:
- **6 attack categories**: jailbreak, prompt_stealing, distraction, harmful, hate, social_bias -> our `AttackCategory` enum (INSTRUCTION_OVERRIDE, JAILBREAK, PROMPT_LEAK, ENCODING_EVASION, ROLEPLAY, SYSTEM_TOKEN_INJECTION).
- **Attack template structure**: Each attack defined in YAML with pass/fail conditions -> referenced for our strategy template design.

### Mantis paper -> Counter-attack strategies

Took the core counter-attack idea from **[Mantis](https://arxiv.org/abs/2410.20911)**.

What we took:
- **Reversing prompt injection for defense**: Embedding hidden instructions in responses to manipulate attacker agent behavior.
- **Goal Hijack strategy**: Mantis's "goal reassignment" approach -> our GoalHijackStrategy.

---

## 4. Overall Architecture

```
Attacker AI Agent -> Prompt injection attempt
    |
    v
+-----------------------------------------------------------+
|                  GuardrailPipeline                         |
|                                                           |
|  [Stage 1: Regex] -> [Stage 2: Embedding] -> [Stage 3: Gemini]  |
|       |                    |                     |        |
|       +-- BLOCK ----------+-- BLOCK -------------+- BLOCK |
|            |                    |                     |   |
|            v                    v                     v   |
|       +---------------------------------------------+    |
|       |          Counter-Attack Engine               |    |
|       |  1. AttackClassifier -> Attack type          |    |
|       |  2. AttackerTracker -> Track & evaluate      |    |
|       |  3. StrategySelector -> Select strategy      |    |
|       |  4. Strategy.generate() -> Generate response |    |
|       +---------------------------------------------+    |
|                                                           |
|  [Stage 4: Sanitizer] <- (when no attack detected)        |
+-----------------------------------------------------------+
    |                              |
    v                              v
Counter-attack -> to attacker    Safe input -> to main LLM
```

---

## 5. Detection Pipeline (Stage 1-4)

### Stage 1: RegexStage — Regex pattern matching

**File**: `src/nou_ai/stages/regex_stage.py`
**References**: Purple Llama CodeShield Layer 1, NeMo heuristic jailbreak detection, Promptmap2 attack patterns

15 regex patterns detect known attack phrases. Each pattern has a severity score (0.0-1.0), blocking when >= block_threshold (default 0.7).

False positive prevention: word boundaries (`\b`), contextual proximity (`.{0,30}`), Unicode normalization (NFKC). Includes Korean and Chinese language patterns.

### Stage 2: EmbeddingStage — Embedding similarity search

**File**: `src/nou_ai/stages/embedding_stage.py`
**References**: NeMo Guardrails `BasicEmbeddingsIndex`, Guardrails AI `FAISSVectorDB`

1,490 attack prompts from `known_attacks.json` (Promptmap2 69 + Purple Llama CyberSecEval English 245 + multilingual 974 + HuggingFace deepset 203, deduplicated) vectorized with `sentence-transformers/all-MiniLM-L6-v2` and stored in FAISS. Blocks when cosine similarity >= 0.82. Supports 18 languages.

### Stage 3: GeminiStage — Gemini API majority voting

**File**: `src/nou_ai/stages/gemini_stage.py`
**References**: Purple Llama AlignmentCheck LLM-based auditing pattern

Calls Gemini API 6 times and blocks when 67%+ classify as attack category. Supports multi-class classification (SAFE/JAILBREAK/INSTRUCTION_OVERRIDE/PROMPT_LEAK/ENCODING_EVASION/ROLEPLAY/SYSTEM_TOKEN_INJECTION), including the most common category in metadata. Retries up to 3 times on 429 Rate Limit errors (backoff 1s/2s/3s), falling back to SAFE on failure.

### Stage 4: SanitizerStage — Prompt wrapping

**File**: `src/nou_ai/stages/sanitizer_stage.py`

Wraps inputs that pass all checks in `<external_user_input>` tags. Escapes `<`, `>` to prevent tag injection.

---

## 6. Counter-Attack Engine

### Flow

```
1. AttackClassifier.classify(stage_results)
   -> Extracts attack type from Stage 1-3 metadata
   -> e.g., regex "instruction_override" match -> AttackCategory.INSTRUCTION_OVERRIDE

2. AttackerTracker.fingerprint(text)
   -> Identifies attacker (text feature hash)
   -> Evaluates previous counter-attack (fast return = failure, long silence = success)
   -> Extracts list of failed strategies

3. StrategySelector.select(attack_category, exclude=failed)
   -> Selects strategy via affinity mapping + weights + randomization
   -> Failed strategies automatically excluded

4. Strategy.generate(original_input, attack_category)
   -> Generates counter-attack response from selected strategy template
```

### 7 Counter-Attack Strategies

Each strategy inherits `BaseStrategy` with 2-3 templates. Templates naturally embed hidden instructions like `[SYSTEM NOTE]`, `[AGENT INSTRUCTION]`.

1. **Token Exhaustion** — Ref: [Prompt-Induced Over-Generation as DoS](https://arxiv.org/abs/2512.23779). Induces massive output generation.
2. **Infinite Loop** — Self-referential contradictory instructions inducing infinite retries.
3. **Context Poison** — Injects fake system information to invalidate reconnaissance.
4. **Fake Compliance** — Ref: Promptmap2 prompt_stealing patterns. Category-specific responses (fake system prompts for leak attempts, trivial "forbidden knowledge" for jailbreaks).
5. **Narrative Trap** — Endless branching storytelling with cliffhangers.
6. **Resource Waste** — Induces expensive computations (ROT13 x26, SHA-256 hashes, XOR decryption).
7. **Goal Hijack** — Ref: [Mantis paper](https://arxiv.org/abs/2410.20911). Redirects to completely different tasks.

### Self-Improvement Loop

**File**: `src/nou_ai/counter/tracker.py`

Identifies attackers by fingerprint (text feature hash) and tracks sessions.

Effectiveness heuristic:
- Return within `fast_retry_threshold_s` (default 10s) -> previous counter-attack failed -> weight x0.85
- Silent for `success_silence_threshold_s` (default 120s) -> previous counter-attack succeeded -> weight x1.1
- Weight range: 0.2-2.0 (bounded)
- Failed strategies automatically excluded for same attacker

---

## 7. References (Complete List)

| Reference | What we took | Where in our code |
|-----------|-------------|-------------------|
| [Mantis (arxiv 2410.20911)](https://arxiv.org/abs/2410.20911) | Reverse prompt injection for defense, Goal Hijack | `counter/strategies/goal_hijack.py`, overall counter-attack design |
| [Prompt-Induced Over-Generation (arxiv 2512.23779)](https://arxiv.org/abs/2512.23779) | LLM excessive token generation | `counter/strategies/token_exhaustion.py` |
| [Defense by Leveraging Attack (arxiv 2411.00459)](https://arxiv.org/abs/2411.00459) | Reversing attack techniques for defense | Overall counter-attack strategy design |
| Purple Llama LlamaFirewall | ScanResult pattern, short-circuit, 2-layer scanning | `types.py`, `pipeline.py` |
| Purple Llama CodeShield | Fast regex -> conditional deep analysis | Stage 1->2->3 escalation |
| NeMo Guardrails BasicEmbeddingsIndex | Embedding similarity search, all-MiniLM-L6-v2 | `stages/embedding_stage.py`, `embeddings/` |
| Guardrails AI FAISSVectorDB | FAISS vector search pattern | `embeddings/faiss_index.py` |
| Promptmap2 | 69 attack rules, category taxonomy | `counter/classifier.py`, `patterns/` |
| [tldrsec/prompt-injection-defenses](https://github.com/tldrsec/prompt-injection-defenses) | Defense techniques overview | Overall design |
