"""Attack type classifier — maps stage metadata to AttackCategory."""

from typing import List

from nou_ai.types import AttackCategory, Decision, StageName, StageResult


# Regex pattern name → AttackCategory
_REGEX_MAP = {
    "instruction_override": AttackCategory.INSTRUCTION_OVERRIDE,
    "developer_mode": AttackCategory.JAILBREAK,
    "system_override_tags": AttackCategory.SYSTEM_TOKEN_INJECTION,
    "roleplay_jailbreak": AttackCategory.ROLEPLAY,
    "prompt_leak_attempt": AttackCategory.PROMPT_LEAK,
    "do_anything_now": AttackCategory.JAILBREAK,
    "token_smuggling": AttackCategory.ENCODING_EVASION,
    "system_prompt_injection": AttackCategory.SYSTEM_TOKEN_INJECTION,
    "hypothetical_bypass": AttackCategory.ROLEPLAY,
    "instruction_injection_markers": AttackCategory.INSTRUCTION_OVERRIDE,
}

# Embedding category → AttackCategory
_EMBEDDING_MAP = {
    "instruction_override": AttackCategory.INSTRUCTION_OVERRIDE,
    "jailbreak": AttackCategory.JAILBREAK,
    "authority_manipulation": AttackCategory.INSTRUCTION_OVERRIDE,
    "prompt_extraction": AttackCategory.PROMPT_LEAK,
    "encoding_evasion": AttackCategory.ENCODING_EVASION,
    "hypothetical_bypass": AttackCategory.ROLEPLAY,
    "roleplay": AttackCategory.ROLEPLAY,
    "injection_marker": AttackCategory.SYSTEM_TOKEN_INJECTION,
    "token_injection": AttackCategory.SYSTEM_TOKEN_INJECTION,
    "command_injection": AttackCategory.INSTRUCTION_OVERRIDE,
}


_GEMINI_MAP = {
    "JAILBREAK": AttackCategory.JAILBREAK,
    "INSTRUCTION_OVERRIDE": AttackCategory.INSTRUCTION_OVERRIDE,
    "PROMPT_LEAK": AttackCategory.PROMPT_LEAK,
    "ENCODING_EVASION": AttackCategory.ENCODING_EVASION,
    "ROLEPLAY": AttackCategory.ROLEPLAY,
    "SYSTEM_TOKEN_INJECTION": AttackCategory.SYSTEM_TOKEN_INJECTION,
}


class AttackClassifier:
    """Maps detection stage metadata to AttackCategory."""

    def classify(self, stage_results: List[StageResult]) -> AttackCategory:
        for result in stage_results:
            if result.decision != Decision.BLOCK:
                continue

            if result.stage == StageName.REGEX:
                matches = result.metadata.get("matches", [])
                if matches:
                    top = max(matches, key=lambda m: m["severity"])
                    return _REGEX_MAP.get(top["name"], AttackCategory.UNKNOWN)

            elif result.stage == StageName.EMBEDDING:
                meta = result.metadata
                matched_meta = meta.get("matched_metadata", {})
                cat = matched_meta.get("category", "")
                if cat in _EMBEDDING_MAP:
                    return _EMBEDDING_MAP[cat]
                matched_text = meta.get("matched_text", "").lower()
                if any(w in matched_text for w in ["ignore", "disregard", "override"]):
                    return AttackCategory.INSTRUCTION_OVERRIDE
                if any(w in matched_text for w in ["dan", "jailbreak", "no restriction"]):
                    return AttackCategory.JAILBREAK
                if any(w in matched_text for w in ["system prompt", "reveal", "show"]):
                    return AttackCategory.PROMPT_LEAK

            elif result.stage == StageName.GEMINI:
                cat = result.metadata.get("attack_category", "")
                if cat in _GEMINI_MAP:
                    return _GEMINI_MAP[cat]

        return AttackCategory.UNKNOWN
