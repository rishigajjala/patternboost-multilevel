from __future__ import annotations

import json
from typing import Any

from multilevel.canonical import canonical_dumps

BOS = "<BOS>"
EOS = "<EOS>"
UNK = "<UNK>"


def instance_to_text(instance: dict[str, Any]) -> str:
    return canonical_dumps(instance)


def text_to_instance(text: str) -> dict[str, Any]:
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("decoded sample is not a JSON object")
    return obj


def text_to_tokens(text: str) -> list[str]:
    return [BOS, *list(text), EOS]


def tokens_to_text(tokens: list[str]) -> str:
    chars = [tok for tok in tokens if tok not in {BOS, EOS, UNK}]
    return "".join(chars)


def instance_to_tokens(instance: dict[str, Any]) -> list[str]:
    return text_to_tokens(instance_to_text(instance))


class Vocabulary:
    def __init__(self, tokens: list[str]):
        unique = [BOS, EOS, UNK]
        seen = set(unique)
        for token in sorted(tokens):
            if token not in seen:
                unique.append(token)
                seen.add(token)
        self.tokens = unique
        self.index = {token: idx for idx, token in enumerate(unique)}

    @classmethod
    def from_texts(cls, texts: list[str]) -> "Vocabulary":
        tokens = []
        for text in texts:
            tokens.extend(text_to_tokens(text))
        return cls(tokens)

    def encode(self, tokens: list[str]) -> list[int]:
        unk = self.index[UNK]
        return [self.index.get(token, unk) for token in tokens]

    def decode(self, ids: list[int]) -> list[str]:
        return [self.tokens[idx] if 0 <= idx < len(self.tokens) else UNK for idx in ids]

    def to_json(self) -> dict[str, Any]:
        return {"schema": "char_vocab_v1", "tokens": self.tokens}

    @classmethod
    def from_json(cls, obj: dict[str, Any]) -> "Vocabulary":
        return cls(list(obj["tokens"]))

