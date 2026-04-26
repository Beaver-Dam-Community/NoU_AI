"""Stage 1: Regex & keyword-based prompt injection detection."""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from nou_ai.types import StageResult, StageName, Decision
from nou_ai.stages.base import BaseStage
from nou_ai.patterns.injection_patterns import DEFAULT_PATTERNS, PatternRule


def _normalize_unicode(text: str) -> str:
    """Normalize unicode to catch fullwidth chars and homoglyphs."""
    return unicodedata.normalize("NFKC", text)


class RegexStage(BaseStage):
    """Fast first-pass detection using curated regex patterns."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(StageName.REGEX, config)
        self.block_threshold: float = self.config.get("block_threshold", 0.7)
        self.patterns: List[PatternRule] = list(DEFAULT_PATTERNS)

        custom_path = self.config.get("custom_patterns_path")
        if custom_path:
            self._load_custom_patterns(custom_path)

    def _load_custom_patterns(self, path: str) -> None:
        """Load additional patterns from a JSON file."""
        import json
        from pathlib import Path

        p = Path(path)
        if not p.exists():
            return
        with open(p) as f:
            data = json.load(f)
        for item in data.get("patterns", []):
            self.patterns.append(PatternRule(**item))

    def add_pattern(self, rule: PatternRule) -> None:
        self.patterns.append(rule)

    def scan(self, text: str) -> StageResult:
        normalized = _normalize_unicode(text)
        matches: List[Dict[str, Any]] = []
        max_severity = 0.0

        for rule in self.patterns:
            if rule.compiled and rule.compiled.search(normalized):
                matches.append({
                    "name": rule.name,
                    "severity": rule.severity,
                    "description": rule.description,
                })
                max_severity = max(max_severity, rule.severity)

        if matches and max_severity >= self.block_threshold:
            top_match = max(matches, key=lambda m: m["severity"])
            return StageResult(
                stage=StageName.REGEX,
                decision=Decision.BLOCK,
                score=max_severity,
                reason=f"Regex match: {top_match['name']} — {top_match['description']}",
                metadata={"matches": matches},
            )

        return StageResult(
            stage=StageName.REGEX,
            decision=Decision.ALLOW,
            score=max_severity,
            reason="No high-severity regex matches" if not matches else f"{len(matches)} low-severity match(es) below threshold",
            metadata={"matches": matches},
        )

    async def scan_async(self, text: str) -> StageResult:
        return self.scan(text)
