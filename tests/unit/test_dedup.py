"""Tests for elsian.acquire.dedup — content-based deduplication."""

from elsian.acquire.dedup import (
    content_hash,
    dedup_texts,
    is_duplicate,
    normalize_text_for_hash,
)


class TestNormalizeTextForHash:
    def test_collapses_whitespace(self) -> None:
        assert normalize_text_for_hash("  hello   world  ") == "hello world"

    def test_lowercases(self) -> None:
        assert normalize_text_for_hash("Hello World") == "hello world"

    def test_empty(self) -> None:
        assert normalize_text_for_hash("") == ""

    def test_none_like(self) -> None:
        assert normalize_text_for_hash(None) == ""  # type: ignore[arg-type]


class TestContentHash:
    def test_stable_hash(self) -> None:
        h1 = content_hash("Revenue: $1,000")
        h2 = content_hash("Revenue: $1,000")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_whitespace_invariant(self) -> None:
        h1 = content_hash("Net income  100")
        h2 = content_hash("  net  income   100  ")
        assert h1 == h2

    def test_empty_returns_empty(self) -> None:
        assert content_hash("") == ""
        assert content_hash("   ") == ""

    def test_different_content_different_hash(self) -> None:
        assert content_hash("revenue 100") != content_hash("revenue 200")


class TestIsDuplicate:
    def test_not_duplicate_when_unseen(self) -> None:
        seen: set[str] = set()
        assert not is_duplicate("hello", seen)

    def test_duplicate_when_seen(self) -> None:
        h = content_hash("hello world")
        seen = {h}
        assert is_duplicate("  Hello  World   ", seen)

    def test_empty_not_duplicate(self) -> None:
        seen = {content_hash("x")}
        assert not is_duplicate("", seen)


class TestDedupTexts:
    def test_removes_duplicates(self) -> None:
        texts = ["Revenue: 100", "Revenue:  100", "Cost: 200"]
        unique, dups = dedup_texts(texts)
        assert len(unique) == 2
        assert 1 in dups  # second was dup of first
        assert unique[0] == "Revenue: 100"
        assert unique[1] == "Cost: 200"

    def test_preserves_order(self) -> None:
        texts = ["A", "B", "C"]
        unique, dups = dedup_texts(texts)
        assert unique == ["A", "B", "C"]
        assert dups == []

    def test_empty_list(self) -> None:
        unique, dups = dedup_texts([])
        assert unique == []
        assert dups == []

    def test_all_same(self) -> None:
        texts = ["same", "SAME", " same "]
        unique, dups = dedup_texts(texts)
        assert len(unique) == 1
        assert len(dups) == 2
