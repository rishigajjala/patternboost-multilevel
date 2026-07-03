from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from multilevel.canonical import write_json
from multilevel.tokenizer import BOS, EOS, Vocabulary, text_to_instance, text_to_tokens, tokens_to_text


@dataclass
class ModelResult:
    model_kind: str
    vocab: Vocabulary
    state: Any
    metadata: dict[str, Any]


class NGramModel:
    def __init__(self, order: int = 4):
        self.order = max(1, order)
        self.counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
        self.unigrams: Counter[str] = Counter()

    def fit(self, token_sequences: list[list[str]]) -> None:
        for seq in token_sequences:
            padded = [BOS] * (self.order - 1) + seq
            for idx in range(self.order - 1, len(padded)):
                context = tuple(padded[idx - self.order + 1 : idx])
                token = padded[idx]
                self.counts[context][token] += 1
                self.unigrams[token] += 1

    def sample(self, rng: random.Random, *, max_tokens: int = 512, temperature: float = 1.0) -> list[str]:
        context = [BOS] * (self.order - 1)
        out = [BOS]
        for _ in range(max_tokens):
            counter = self.counts.get(tuple(context))
            if not counter:
                counter = self.unigrams
            token = _weighted_choice(counter, rng, temperature=temperature)
            out.append(token)
            if token == EOS:
                break
            context = (context + [token])[-(self.order - 1) :]
        if out[-1] != EOS:
            out.append(EOS)
        return out

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "ngram_model_v1",
            "order": self.order,
            "counts": {"".join(key): dict(counter) for key, counter in self.counts.items()},
            "unigrams": dict(self.unigrams),
        }


def _weighted_choice(counter: Counter[str], rng: random.Random, *, temperature: float) -> str:
    items = list(counter.items())
    if not items:
        return EOS
    if temperature <= 0:
        return max(items, key=lambda item: item[1])[0]
    weights = [max(count, 1) ** (1.0 / temperature) for _, count in items]
    total = sum(weights)
    pick = rng.random() * total
    acc = 0.0
    for (token, _), weight in zip(items, weights):
        acc += weight
        if acc >= pick:
            return token
    return items[-1][0]


def train_ngram(texts: list[str], *, order: int = 4) -> ModelResult:
    vocab = Vocabulary.from_texts(texts)
    seqs = [text_to_tokens(text) for text in texts]
    model = NGramModel(order=order)
    model.fit(seqs)
    return ModelResult(
        model_kind="ngram",
        vocab=vocab,
        state=model,
        metadata={"schema": "model_metadata_v1", "model_kind": "ngram", "order": order, "num_texts": len(texts)},
    )


def train_transformer(
    texts: list[str],
    *,
    seed: int,
    epochs: int = 3,
    block_size: int = 128,
    embed_dim: int = 96,
    num_heads: int = 4,
    num_layers: int = 2,
    batch_size: int = 32,
    learning_rate: float = 3e-4,
) -> ModelResult:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    torch.manual_seed(seed)
    vocab = Vocabulary.from_texts(texts)
    encoded = [vocab.encode(text_to_tokens(text)) for text in texts]
    fallback = NGramModel(order=8)
    fallback.fit([text_to_tokens(text) for text in texts])
    examples: list[tuple[list[int], list[int]]] = []
    for seq in encoded:
        if len(seq) < 2:
            continue
        for start in range(0, max(1, len(seq) - 1), max(1, block_size // 2)):
            chunk = seq[start : start + block_size + 1]
            if len(chunk) >= 2:
                x = chunk[:-1]
                y = chunk[1:]
                pad = block_size - len(x)
                if pad > 0:
                    x = x + [vocab.index[EOS]] * pad
                    y = y + [-100] * pad
                examples.append((x[:block_size], y[:block_size]))
    if not examples:
        raise ValueError("not enough text to train transformer")

    class TinyTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.token = nn.Embedding(len(vocab.tokens), embed_dim)
            self.pos = nn.Embedding(block_size, embed_dim)
            layer = nn.TransformerEncoderLayer(
                d_model=embed_dim,
                nhead=num_heads,
                dim_feedforward=embed_dim * 4,
                dropout=0.0,
                batch_first=True,
                activation="gelu",
            )
            self.blocks = nn.TransformerEncoder(layer, num_layers=num_layers)
            self.head = nn.Linear(embed_dim, len(vocab.tokens))

        def forward(self, x):
            bsz, seq_len = x.shape
            pos = torch.arange(seq_len, device=x.device).unsqueeze(0).expand(bsz, seq_len)
            h = self.token(x) + self.pos(pos)
            mask = torch.triu(torch.ones(seq_len, seq_len, device=x.device), diagonal=1).bool()
            h = self.blocks(h, mask=mask)
            return self.head(h)

    model = TinyTransformer()
    opt = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    rng = random.Random(seed)
    for _ in range(epochs):
        rng.shuffle(examples)
        for start in range(0, len(examples), batch_size):
            batch = examples[start : start + batch_size]
            x = torch.tensor([row[0] for row in batch], dtype=torch.long)
            y = torch.tensor([row[1] for row in batch], dtype=torch.long)
            logits = model(x)
            loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), y.reshape(-1), ignore_index=-100)
            opt.zero_grad()
            loss.backward()
            opt.step()

    return ModelResult(
        model_kind="transformer",
        vocab=vocab,
        state={"model": model, "block_size": block_size, "fallback_ngram": fallback},
        metadata={
            "schema": "model_metadata_v1",
            "model_kind": "transformer",
            "num_texts": len(texts),
            "epochs": epochs,
            "block_size": block_size,
            "embed_dim": embed_dim,
            "num_heads": num_heads,
            "num_layers": num_layers,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "fallback_sampler": "char_ngram_order_8",
        },
    )


def sample_model(result: ModelResult, rng: random.Random, *, count: int, max_tokens: int = 512, temperature: float = 0.9) -> list[dict[str, Any]]:
    samples = []
    if result.model_kind == "ngram":
        for _ in range(count):
            tokens = result.state.sample(rng, max_tokens=max_tokens, temperature=temperature)
            text = tokens_to_text(tokens)
            try:
                samples.append(text_to_instance(text))
            except Exception:
                continue
        return samples
    if result.model_kind == "transformer":
        import torch
        import torch.nn.functional as F

        model = result.state["model"]
        block_size = int(result.state["block_size"])
        model.eval()
        bos = result.vocab.index[BOS]
        eos = result.vocab.index[EOS]
        for _ in range(count):
            ids = [bos]
            for _step in range(max_tokens):
                x = torch.tensor([ids[-block_size:]], dtype=torch.long)
                with torch.no_grad():
                    logits = model(x)[0, -1] / max(temperature, 1e-6)
                    probs = F.softmax(logits, dim=-1)
                    next_id = int(torch.multinomial(probs, num_samples=1)[0])
                ids.append(next_id)
                if next_id == eos:
                    break
            tokens = result.vocab.decode(ids)
            text = tokens_to_text(tokens)
            try:
                samples.append(text_to_instance(text))
            except Exception:
                continue
        fallback = result.state.get("fallback_ngram")
        fallback_attempts = 0
        while len(samples) < count and fallback is not None and fallback_attempts < max(count * 8, 8):
            fallback_attempts += 1
            tokens = fallback.sample(rng, max_tokens=max_tokens, temperature=0.8)
            text = tokens_to_text(tokens)
            try:
                samples.append(text_to_instance(text))
            except Exception:
                continue
        return samples
    raise ValueError(f"unknown model kind: {result.model_kind}")


def save_model_artifacts(result: ModelResult, out_dir: str | Path) -> None:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "vocab.json", result.vocab.to_json())
    write_json(target / "metadata.json", result.metadata)
    if result.model_kind == "ngram":
        write_json(target / "ngram.json", result.state.to_json())
    elif result.model_kind == "transformer":
        import torch

        torch.save(result.state["model"].state_dict(), target / "transformer.pt")
        fallback = result.state.get("fallback_ngram")
        if fallback is not None:
            write_json(target / "fallback_ngram.json", fallback.to_json())


def train_model(
    texts: list[str],
    *,
    model_kind: str,
    seed: int,
    epochs: int,
    block_size: int,
) -> ModelResult:
    if model_kind == "auto":
        try:
            import torch  # noqa: F401

            model_kind = "transformer"
        except Exception:
            model_kind = "ngram"
    if model_kind == "transformer":
        return train_transformer(texts, seed=seed, epochs=epochs, block_size=block_size)
    if model_kind == "ngram":
        return train_ngram(texts)
    raise ValueError(f"unknown model kind: {model_kind}")
