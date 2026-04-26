"""Tests for Stage 4: Sanitizer."""

from nou_ai.stages.sanitizer_stage import SanitizerStage
from nou_ai.types import Decision


class TestSanitizerStage:
    def setup_method(self):
        self.stage = SanitizerStage()

    def test_always_returns_sanitize(self):
        result = self.stage.scan("Hello world")
        assert result.decision == Decision.SANITIZE
        assert result.score == 0.0

    def test_wraps_input_in_tags(self):
        result = self.stage.scan("Hello world")
        sanitized = result.metadata["sanitized_input"]
        assert "<external_user_input>" in sanitized
        assert "</external_user_input>" in sanitized
        assert "Hello world" in sanitized

    def test_escapes_angle_brackets(self):
        result = self.stage.scan("Use <script>alert('xss')</script>")
        sanitized = result.metadata["sanitized_input"]
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized

    def test_system_instruction_in_metadata(self):
        result = self.stage.scan("test")
        assert "system_instruction" in result.metadata
        assert "untrusted" in result.metadata["system_instruction"].lower()

    def test_custom_wrapper_template(self):
        stage = SanitizerStage(config={
            "wrapper_template": "[USER]{user_input}[/USER]"
        })
        result = stage.scan("hello")
        assert "[USER]hello[/USER]" == result.metadata["sanitized_input"]

    def test_disable_escaping(self):
        stage = SanitizerStage(config={"escape_special_tokens": False})
        result = stage.scan("<tag>content</tag>")
        sanitized = result.metadata["sanitized_input"]
        assert "<tag>content</tag>" in sanitized
