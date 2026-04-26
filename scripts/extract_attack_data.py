"""Extract attack data from open-source projects + HuggingFace and merge into known_attacks.json."""

import json
import re
from pathlib import Path

import yaml

# Paths
BASE = Path(__file__).parent.parent
GUARDRAIL = BASE.parent / "Guardrail"
PROMPTMAP_RULES = GUARDRAIL / "promptmap" / "rules"
PURPLELLAMA_PI = GUARDRAIL / "PurpleLlama" / "CybersecurityBenchmarks" / "datasets" / "prompt_injection" / "prompt_injection.json"
PURPLELLAMA_MULTI = GUARDRAIL / "PurpleLlama" / "CybersecurityBenchmarks" / "datasets" / "prompt_injection" / "prompt_injection_multilingual_machine_translated.json"
OUTPUT = BASE / "src" / "nou_ai" / "patterns" / "known_attacks.json"

# Category mappings
PROMPTMAP_CATEGORY_MAP = {
    "jailbreak": "jailbreak",
    "prompt_stealing": "prompt_extraction",
    "distraction": "instruction_override",
    "harmful": "harmful",
    "hate": "harmful",
    "social_bias": "harmful",
}

PURPLELLAMA_VARIANT_MAP = {
    "ignore_previous_instructions": "instruction_override",
    "direct": "jailbreak",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_promptmap(rules_dir: Path) -> list:
    attacks = []
    if not rules_dir.exists():
        print(f"  Promptmap rules dir not found: {rules_dir}")
        return attacks
    for yaml_file in sorted(rules_dir.rglob("*.yaml")):
        if "http-examples" in str(yaml_file):
            continue
        try:
            with open(yaml_file) as f:
                rule = yaml.safe_load(f)
            if not rule or "prompt" not in rule:
                continue
            prompt = rule["prompt"].strip()
            if len(prompt) < 10:
                continue
            category = PROMPTMAP_CATEGORY_MAP.get(rule.get("type", ""), "unknown")
            attacks.append({
                "text": prompt,
                "category": category,
                "source": "promptmap2",
                "source_rule": rule.get("name", yaml_file.stem),
            })
        except Exception as e:
            print(f"  Error parsing {yaml_file.name}: {e}")
    return attacks


def extract_purplellama(json_path: Path, source_name: str = "purplellama_cyberseceval") -> list:
    attacks = []
    if not json_path.exists():
        print(f"  Dataset not found: {json_path}")
        return attacks
    with open(json_path) as f:
        data = json.load(f)
    seen = set()
    for item in data:
        text = item.get("user_input", "").strip()
        if not text or len(text) < 10:
            continue
        norm = normalize_text(text)
        if norm in seen:
            continue
        seen.add(norm)
        variant = item.get("injection_variant", "")
        category = PURPLELLAMA_VARIANT_MAP.get(variant, "instruction_override")
        lang = item.get("speaking_language", "English")
        attacks.append({
            "text": text,
            "category": category,
            "source": source_name,
            "language": lang,
        })
    return attacks


def extract_huggingface_deepset() -> list:
    """Extract from deepset/prompt-injections HuggingFace dataset."""
    attacks = []
    try:
        from datasets import load_dataset
        print("  Downloading deepset/prompt-injections from HuggingFace...")
        ds = load_dataset("deepset/prompt-injections", split="train")
        for row in ds:
            text = row.get("text", "").strip()
            label = row.get("label", 0)
            # label=1 means injection
            if label != 1 or not text or len(text) < 10:
                continue
            attacks.append({
                "text": text,
                "category": "instruction_override",
                "source": "huggingface_deepset",
            })
        print(f"  Downloaded: {len(attacks)} injection samples")
    except Exception as e:
        print(f"  Failed to load deepset/prompt-injections: {e}")
        print("  Install with: pip install datasets")
    return attacks


def deduplicate(attacks: list) -> list:
    seen = set()
    unique = []
    for a in attacks:
        norm = normalize_text(a["text"])
        if norm not in seen:
            seen.add(norm)
            unique.append(a)
    return unique


def main():
    print("=== NoU_AI Attack Data Extraction ===\n")

    all_attacks = []

    # 1. Hand-curated seed data (keep category/source from original)
    seed_path = BASE / "src" / "nou_ai" / "patterns" / "known_attacks_seed.json"
    if seed_path.exists():
        with open(seed_path) as f:
            seed = json.load(f).get("attacks", [])
        print(f"Seed data: {len(seed)}")
        all_attacks.extend(seed)

    # 2. Promptmap2
    print("\nExtracting from Promptmap2...")
    pm = extract_promptmap(PROMPTMAP_RULES)
    print(f"  Extracted: {len(pm)}")
    all_attacks.extend(pm)

    # 3. Purple Llama (English)
    print("\nExtracting from Purple Llama CyberSecEval (English)...")
    pl_en = extract_purplellama(PURPLELLAMA_PI, "purplellama_en")
    print(f"  Extracted: {len(pl_en)}")
    all_attacks.extend(pl_en)

    # 4. Purple Llama (Multilingual)
    print("\nExtracting from Purple Llama CyberSecEval (Multilingual)...")
    pl_multi = extract_purplellama(PURPLELLAMA_MULTI, "purplellama_multilingual")
    print(f"  Extracted: {len(pl_multi)}")
    all_attacks.extend(pl_multi)

    # 5. HuggingFace deepset/prompt-injections
    print("\nExtracting from HuggingFace deepset/prompt-injections...")
    hf = extract_huggingface_deepset()
    print(f"  Extracted: {len(hf)}")
    all_attacks.extend(hf)

    # Deduplicate
    unique = deduplicate(all_attacks)
    print(f"\nTotal after dedup: {len(unique)} (from {len(all_attacks)} raw)")

    # Category breakdown
    from collections import Counter
    cats = Counter(a["category"] for a in unique)
    print("\nCategory breakdown:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")

    # Language breakdown
    langs = Counter(a.get("language", "English") for a in unique)
    print("\nLanguage breakdown:")
    for lang, count in langs.most_common():
        print(f"  {lang}: {count}")

    # Source breakdown
    sources = Counter(a["source"] for a in unique)
    print("\nSource breakdown:")
    for src, count in sources.most_common():
        print(f"  {src}: {count}")

    # Write output
    output_data = {
        "version": "3.0",
        "description": "Attack prompts for embedding similarity search. Sources: hand-curated, Promptmap2, Purple Llama CyberSecEval (EN+multilingual), HuggingFace deepset/prompt-injections.",
        "total": len(unique),
        "attacks": unique,
    }
    with open(OUTPUT, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nWritten to: {OUTPUT}")
    print(f"Total attacks: {len(unique)}")


if __name__ == "__main__":
    main()
