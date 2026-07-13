from __future__ import annotations

import random

import pytest

from multilevel.modeling import sample_model, train_transformer
from multilevel.tokenizer import instance_to_text


def test_transformer_sampling_has_valid_json_fallback():
    pytest.importorskip("torch")
    texts = [
        instance_to_text(
            {
                "schema": "misr_instance_v1",
                "rectangles": [[idx, idx + 2, 0, 1], [idx + 2, idx + 3, 1, 3]],
            }
        )
        for idx in range(12)
    ]
    model = train_transformer(
        texts,
        seed=7,
        epochs=1,
        block_size=128,
        embed_dim=32,
        num_heads=4,
        num_layers=1,
        batch_size=4,
    )
    samples = sample_model(model, random.Random(7), count=6, max_tokens=512)
    assert samples
    assert all(isinstance(sample, dict) for sample in samples)
    assert model.metadata["embed_dim"] == 32
    assert model.metadata["num_heads"] == 4
    assert model.metadata["num_layers"] == 1
    assert model.metadata["num_parameters"] > 0


def test_transformer_rejects_incompatible_width_and_heads():
    pytest.importorskip("torch")
    with pytest.raises(ValueError, match="divisible"):
        train_transformer(
            ["{}", "{}"],
            seed=1,
            epochs=1,
            embed_dim=30,
            num_heads=4,
        )
