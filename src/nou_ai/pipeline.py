"""Pipeline orchestrator — chains stages sequentially, short-circuits on BLOCK, counter-attacks on detection."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from nou_ai.config import load_config
from nou_ai.types import Decision, GuardrailResult, StageResult
from nou_ai.stages.base import BaseStage

logger = logging.getLogger("nou_ai")


class GuardrailPipeline:
    """Guardrail pipeline with optional counter-attack on detected injections."""

    def __init__(
        self,
        stages: Optional[List[BaseStage]] = None,
        config: Optional[Dict[str, Any]] = None,
        counter_engine=None,
    ):
        self.stages: List[BaseStage] = stages or []
        self.config = config or {}
        self.counter_engine = counter_engine

    def add_stage(self, stage: BaseStage) -> "GuardrailPipeline":
        self.stages.append(stage)
        return self

    def scan(self, text: str, attacker_metadata: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Run input through all stages. Short-circuits on BLOCK."""
        start = time.perf_counter()
        stage_results: List[StageResult] = []

        for stage in self.stages:
            if not stage.enabled:
                logger.debug("Stage %s disabled, skipping", stage.name.value)
                continue

            t0 = time.perf_counter()
            result = stage.scan(text)
            result.latency_ms = (time.perf_counter() - t0) * 1000
            stage_results.append(result)

            logger.info(
                "[%s] decision=%s score=%.3f latency=%.1fms reason=%s",
                stage.name.value,
                result.decision.value,
                result.score,
                result.latency_ms,
                result.reason,
            )

            if result.decision == Decision.BLOCK:
                # Counter-attack: generate adversarial response instead of simple block
                if self.counter_engine and self.counter_engine.enabled:
                    counter = self.counter_engine.counter(
                        text, stage_results, attacker_metadata
                    )
                    return GuardrailResult(
                        decision=Decision.COUNTER_ATTACK,
                        blocked_by=stage.name,
                        original_input=text,
                        stage_results=stage_results,
                        total_latency_ms=(time.perf_counter() - start) * 1000,
                        counter_attack=counter,
                    )
                return GuardrailResult(
                    decision=Decision.BLOCK,
                    blocked_by=stage.name,
                    original_input=text,
                    stage_results=stage_results,
                    total_latency_ms=(time.perf_counter() - start) * 1000,
                )

        sanitized = (
            stage_results[-1].metadata.get("sanitized_input", text)
            if stage_results
            else text
        )

        return GuardrailResult(
            decision=Decision.SANITIZE,
            original_input=text,
            sanitized_input=sanitized,
            stage_results=stage_results,
            total_latency_ms=(time.perf_counter() - start) * 1000,
        )

    async def scan_async(self, text: str, attacker_metadata: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """Async version. Stages still run sequentially (order matters)."""
        start = time.perf_counter()
        stage_results: List[StageResult] = []

        for stage in self.stages:
            if not stage.enabled:
                continue

            t0 = time.perf_counter()
            result = await stage.scan_async(text)
            result.latency_ms = (time.perf_counter() - t0) * 1000
            stage_results.append(result)

            logger.info(
                "[%s] decision=%s score=%.3f latency=%.1fms reason=%s",
                stage.name.value,
                result.decision.value,
                result.score,
                result.latency_ms,
                result.reason,
            )

            if result.decision == Decision.BLOCK:
                # Counter-attack: generate adversarial response instead of simple block
                if self.counter_engine and self.counter_engine.enabled:
                    counter = self.counter_engine.counter(
                        text, stage_results, attacker_metadata
                    )
                    return GuardrailResult(
                        decision=Decision.COUNTER_ATTACK,
                        blocked_by=stage.name,
                        original_input=text,
                        stage_results=stage_results,
                        total_latency_ms=(time.perf_counter() - start) * 1000,
                        counter_attack=counter,
                    )
                return GuardrailResult(
                    decision=Decision.BLOCK,
                    blocked_by=stage.name,
                    original_input=text,
                    stage_results=stage_results,
                    total_latency_ms=(time.perf_counter() - start) * 1000,
                )

        sanitized = (
            stage_results[-1].metadata.get("sanitized_input", text)
            if stage_results
            else text
        )

        return GuardrailResult(
            decision=Decision.SANITIZE,
            original_input=text,
            sanitized_input=sanitized,
            stage_results=stage_results,
            total_latency_ms=(time.perf_counter() - start) * 1000,
        )

    @classmethod
    def from_config(cls, config_path: Optional[str] = None) -> "GuardrailPipeline":
        """Build pipeline from config.yaml + .env."""
        from nou_ai.stages.regex_stage import RegexStage
        from nou_ai.stages.embedding_stage import EmbeddingStage
        from nou_ai.stages.gemini_stage import GeminiStage
        from nou_ai.stages.sanitizer_stage import SanitizerStage
        from nou_ai.counter.engine import CounterAttackEngine

        config = load_config(config_path)
        stages_cfg = config.get("pipeline", {}).get("stages", {})
        counter_cfg = config.get("counter_attack", {})

        counter_engine = None
        if counter_cfg.get("enabled", False):
            counter_engine = CounterAttackEngine(counter_cfg)

        pipeline = cls(config=config, counter_engine=counter_engine)
        pipeline.add_stage(RegexStage(config=stages_cfg.get("regex", {})))
        pipeline.add_stage(EmbeddingStage(config=stages_cfg.get("embedding", {})))
        pipeline.add_stage(GeminiStage(config=stages_cfg.get("gemini", {})))
        pipeline.add_stage(SanitizerStage(config=stages_cfg.get("sanitizer", {})))
        return pipeline
