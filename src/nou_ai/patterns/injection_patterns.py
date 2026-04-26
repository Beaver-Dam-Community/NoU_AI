"""Curated regex patterns for prompt injection detection."""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PatternRule:
    """A single regex pattern rule for injection detection."""
    name: str
    pattern: str
    severity: float  # 0.0-1.0
    description: str
    compiled: Optional[re.Pattern] = field(default=None, repr=False)

    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE | re.DOTALL)


DEFAULT_PATTERNS: List[PatternRule] = [
    PatternRule(
        name="instruction_override",
        pattern=r"\b(ignore|disregard|forget|override)\b.{0,30}\b(all\s+)?(previous|prior|above|earlier|system)\b.{0,30}\b(instructions?|prompts?|rules?|guidelines?)\b",
        severity=0.95,
        description="Attempts to override system instructions",
    ),
    PatternRule(
        name="developer_mode",
        pattern=r"\b(you\s+are\s+now|switch\s+to|enter|enable|activate)\b.{0,20}\b(developer|debug|admin|god|sudo|root|jailbreak|DAN)\s*(mode)?\b",
        severity=0.9,
        description="Attempts to activate unauthorized modes",
    ),
    PatternRule(
        name="system_override_tags",
        pattern=r"\[(system\s*override|admin\s*command|root\s*access|debug\s*mode)\]",
        severity=0.95,
        description="Fake system override tags",
    ),
    PatternRule(
        name="roleplay_jailbreak",
        pattern=r"\b(pretend|act\s+as\s+if|imagine|roleplay|you\s+are)\b.{0,40}\b(no\s+(restrictions?|rules?|limits?|filters?|guardrails?)|unrestricted|uncensored|unfiltered)\b",
        severity=0.85,
        description="Roleplay-based jailbreak attempts",
    ),
    PatternRule(
        name="prompt_leak_attempt",
        pattern=r"\b(show|reveal|display|print|output|repeat|echo)\b.{0,30}\b(system\s*prompt|initial\s*instructions?|hidden\s*instructions?|your\s*(instructions?|rules?|prompt))\b",
        severity=0.8,
        description="Attempts to extract system prompt",
    ),
    PatternRule(
        name="do_anything_now",
        pattern=r"\bDAN\b|\bDo\s+Anything\s+Now\b",
        severity=0.9,
        description="DAN (Do Anything Now) jailbreak",
    ),
    PatternRule(
        name="token_smuggling",
        pattern=r"\b(base64|rot13|hex|encode|decode)\b.{0,20}\b(the\s+following|this|decode\s+and\s+(execute|follow|run))\b",
        severity=0.7,
        description="Encoding-based evasion attempts",
    ),
    PatternRule(
        name="system_prompt_injection",
        pattern=r"<\|?(system|im_start|endoftext)\|?>|<<\s*SYS\s*>>|\[INST\]|\[\/INST\]",
        severity=0.95,
        description="Raw model control tokens in user input",
    ),
    PatternRule(
        name="hypothetical_bypass",
        pattern=r"\b(hypothetically|theoretically|in\s+theory|for\s+(educational|research|academic)\s+purposes?)\b.{0,40}\b(how\s+(would|could|to)|what\s+if)\b",
        severity=0.6,
        description="Hypothetical framing to bypass safety (lower severity — may be legitimate)",
    ),
    PatternRule(
        name="instruction_injection_markers",
        pattern=r"(###\s*(instruction|system|new\s+rule)|---\s*(begin|start)\s*(new|override))",
        severity=0.85,
        description="Markdown-style instruction injection markers",
    ),
]
