"""LLM API client supporting Anthropic and OpenAI-compatible APIs."""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    content: str
    parsed_json: dict | None = None
    model: str = ""
    usage: dict = None


class LLMClient:
    """Unified LLM client. Uses Anthropic SDK by default, falls back to OpenAI-compatible."""

    def __init__(self, provider: str = "anthropic", model: str | None = None,
                 api_key: str | None = None, base_url: str | None = None):
        self.provider = provider
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL")

        if provider == "anthropic":
            self.model = model or os.environ.get("ANTHROPIC_MODEL", "deepseek-v4-flash")
        else:
            self.model = model or os.environ.get("OPENAI_MODEL", "deepseek-v4-flash")

        # Auto-detect DeepSeek: use OpenAI-compatible endpoint (more stable)
        if self.model and "deepseek" in self.model.lower():
            self.provider = "openai"
            if not base_url and not os.environ.get("OPENAI_BASE_URL"):
                self.base_url = "https://api.deepseek.com/v1"

    def chat(self, system_prompt: str, user_message: str,
             temperature: float = 0.7, max_tokens: int = 2048) -> LLMResponse:
        """Send a chat completion request and parse the response.
        Retries once on failure, returns empty response on persistent error."""
        for attempt in range(2):
            try:
                if self.provider == "anthropic":
                    return self._chat_anthropic(system_prompt, user_message, temperature, max_tokens)
                else:
                    return self._chat_openai(system_prompt, user_message, temperature, max_tokens)
            except Exception as e:
                if attempt == 0:
                    import time
                    time.sleep(3)
                else:
                    print(f"  [API FAIL] {e}")
        return LLMResponse(content="{}", parsed_json={})

    def _chat_anthropic(self, system: str, user: str, temperature: float, max_tokens: int) -> LLMResponse:
        try:
            import anthropic
            kwargs = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            client = anthropic.Anthropic(**kwargs)
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text_parts = []
            for block in message.content:
                if hasattr(block, 'text'):
                    text_parts.append(block.text)
                elif hasattr(block, 'thinking'):
                    # DeepSeek/thinking models: capture thinking for debugging
                    text_parts.append(block.thinking)
            content = "".join(text_parts)
            usage = {}
            if hasattr(message, 'usage') and message.usage:
                usage = {"input": message.usage.input_tokens, "output": message.usage.output_tokens}
            return LLMResponse(
                content=content,
                parsed_json=self._extract_json(content),
                model=self.model,
                usage=usage,
            )
        except ImportError:
            return self._chat_openai(system, user, temperature, max_tokens)
        except Exception as e:
            print(f"  [API ERR] {e}")
            return LLMResponse(content="{}", parsed_json={})

    def _chat_openai(self, system: str, user: str, temperature: float, max_tokens: int) -> LLMResponse:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            stream = client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=True,
            )
            content = ""
            thinking = ""
            think_buf = ""
            print("\n[LLM STREAM] ", end="", flush=True)
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content
                    print(delta.content, end="", flush=True)
                # DeepSeek thinking blocks - buffer and print complete lines
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    thinking += delta.reasoning_content
                    think_buf += delta.reasoning_content
                    if '\n' in think_buf or len(think_buf) > 200:
                        print(f"\n[THINK] {think_buf.strip()}", flush=True)
                        think_buf = ""
            if think_buf.strip():
                print(f"\n[THINK] {think_buf.strip()}", flush=True)
            print()  # newline after stream ends
            return LLMResponse(
                content=content,
                parsed_json=self._extract_json(content),
                model=self.model,
                usage={},
            )
        except ImportError:
            print("  [WARN] Neither anthropic nor openai SDK installed. pip install anthropic")
            return LLMResponse(content="{}", parsed_json={})
        except Exception as e:
            print(f"  [API ERR] {e}")
            return LLMResponse(content="{}", parsed_json={})

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Extract JSON from LLM output that may have markdown code blocks."""
        # Try to find JSON in code blocks first (with or without closing ```)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)(?:```|$)', text)
        if json_match:
            text = json_match.group(1)

        # Try to find the outermost JSON object
        try:
            start = text.find('{')
            if start == -1:
                return None
            depth = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            json_str = text[start:end]
            # Remove trailing commas before } or ] (common LLM mistake)
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            preview = text[:300].replace('\n', ' ')
            print(f"  [JSON ERR] {e} | text: {preview}...")
            return None
        except Exception as e:
            preview = text[:300].replace('\n', ' ')
            print(f"  [EXTRACT ERR] {e} | text: {preview}...")
            return None
