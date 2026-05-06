"""WordIndexer 单测：拼全文 + offset → polygon 反查 + line/block fallback。"""

import json
from pathlib import Path

import pytest

from app.services.kie.word_indexer import WordIndexer

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def invoice_layout():
    return json.loads((FIXTURES / "pp_structure_invoice.json").read_text(encoding="utf-8"))


@pytest.fixture
def indexer(invoice_layout):
    return WordIndexer.from_layout(invoice_layout)


class TestFromLayout:
    def test_content_concatenates_blocks_in_reading_order(self, indexer):
        assert "Contoso INVOICE" in indexer.content
        assert "Invoice No 12345678" in indexer.content
        assert "Total GBP 180.00" in indexer.content

    def test_content_uses_newline_between_blocks(self, indexer):
        assert "INVOICE\nVAT" in indexer.content

    def test_words_have_aligned_offsets(self, indexer):
        for w in indexer.words:
            assert indexer.content[w.offset : w.offset + w.length] == w.text

    def test_handles_empty_layout(self):
        wi = WordIndexer.from_layout({})
        assert wi.content == ""
        assert wi.words == []

    def test_handles_none_layout(self):
        wi = WordIndexer.from_layout(None)
        assert wi.content == ""
        assert wi.words == []


class TestLookupByOffset:
    def test_lookup_returns_block_polygon(self, indexer):
        # "12345678" 在 content 中的位置
        idx = indexer.content.find("12345678")
        assert idx >= 0
        regions, spans = indexer.lookup_by_offset(idx, idx + 8)
        assert len(regions) >= 1
        assert regions[0].pageNumber == 1
        assert len(regions[0].polygon) == 8
        assert len(spans) == 1

    def test_lookup_invalid_range_returns_empty(self, indexer):
        regions, spans = indexer.lookup_by_offset(-1, 10)
        assert regions == [] and spans == []
        regions, spans = indexer.lookup_by_offset(10, 10)
        assert regions == [] and spans == []


class TestLookupByText:
    def test_finds_substring(self, indexer):
        regions, spans = indexer.lookup_by_text("180.00")
        assert len(regions) >= 1
        assert len(spans) == 1

    def test_text_not_found_returns_empty(self, indexer):
        regions, spans = indexer.lookup_by_text("not-in-content-XYZ")
        assert regions == [] and spans == []
