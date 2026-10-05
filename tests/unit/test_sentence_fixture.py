"""分句双端一致性（服务端侧）：_split_complete_sentences 对照共享 fixture。

fixture（tests/frontend/fixtures/sentences.json）同时被前端特征测试
（tests/frontend/sentences.test.mjs）消费。任何一端改分句语义必须同步
fixture 与另一端实现——对端测试会红。差异语义见 fixture._comment。
"""

import json
from pathlib import Path

from psych_support_bot.services.conversation import _split_complete_sentences

FIXTURE = Path(__file__).resolve().parent.parent / "frontend" / "fixtures" / "sentences.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_golden_both_agree() -> None:
    """纯句末标点文本：两个实现必须逐字一致（分句语义的共同基线）。"""
    for case in _fixture()["golden_both_agree"]:
        got_first, rest_first = _split_complete_sentences(case["input"], first=True)
        got_later, rest_later = _split_complete_sentences(case["input"], first=False)
        assert got_first == case["expected"], case["name"]
        assert got_later == case["expected"], case["name"]
        assert rest_first == rest_later == "", case["name"]


def test_server_semantics() -> None:
    """服务端口径：首句软切阈值 14 / 后续句 56 / 无标点返回累积余量。"""
    for case in _fixture()["server_only"]:
        got, rest = _split_complete_sentences(case["input"], first=case["first"])
        assert got == case["expected_sentences"], case["name"]
        assert rest == case["expected_remainder"], case["name"]
