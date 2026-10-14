"""Offline contract tests: no model weights, network requests, or API keys."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image
from pydantic import BaseModel, ValidationError

from marker.processors.llm.llm_table_json import LLMTableJSONProcessor
from marker.output import save_output
from marker.renderers.json import JSONRenderer
from marker.renderers.markdown import MarkdownRenderer
from marker.schema.blocks import Table
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from marker.services.openai import OpenAIService
from marker.tables.render import render_table
from marker.tables.geometry import CAPTION
from marker.tables.schema import TableReconstruction
from marker.tables.stitch import stitch_tables
from marker.tables.validation import validate_reconstruction


def geometry(region_id, page, text="А"):
    return {"region": {"region_id": region_id, "page": page, "bbox": [0, 0, 100, 100]},
            "text_blocks": [{"id": region_id + ":b0", "region_id": region_id, "page": page,
                             "bbox": [5, 5, 20, 15], "text": text, "type": "text", "source": "pdftext"}],
            "rules": [], "caption_hint": "", "warnings": []}


def reconstruction(sources):
    cells, rows = [], []
    for r, g in enumerate(sources):
        region = dict(g["region"], bbox=[0, 0, 100, 20])
        cells.append(dict(r=r, c=0, role="data", kind="text", text=g["text_blocks"][0]["text"],
                          regions=[region], blocks=[g["text_blocks"][0]["id"]]))
        rows.append(dict(region, r=r))
    return TableReconstruction.model_validate({"schema_version": "1.1", "tables": [
        {"number": "И.3", "pages": [g["region"]["page"] for g in sources],
         "regions": [g["region"] for g in sources], "truncated_start": False, "truncated_end": False,
         "n_rows": len(sources), "n_cols": 1, "header_rows": 0, "row_regions": rows,
         "column_regions": [dict(g["region"], c=0) for g in sources], "cells": cells}],
        "unassigned_blocks": [], "warnings": []})


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.sources = [geometry("a", 1), geometry("b", 2, "Б")]
        self.result = reconstruction(self.sources)

    def test_complete_geometry_and_provenance(self):
        self.assertEqual(validate_reconstruction(self.result, self.sources), ([], []))

    def test_schema_rejects_unknown_fields_and_string_indices(self):
        value = self.result.model_dump()
        value["tables"][0]["cells"][0]["r"] = "0"
        with self.assertRaises(ValidationError):
            TableReconstruction.model_validate(value)
        value = self.result.model_dump()
        value["invented"] = True
        with self.assertRaises(ValidationError):
            TableReconstruction.model_validate(value)

    def test_overlap_is_rejected(self):
        self.result.tables[0].cells[0].rowspan = 2
        errors, _ = validate_reconstruction(self.result, self.sources)
        self.assertTrue(any("span intersection" in e for e in errors))

    def test_missing_and_duplicate_source_blocks_are_rejected(self):
        self.result.tables[0].cells[0].blocks = []
        self.result.tables[0].cells[1].blocks *= 2
        errors, _ = validate_reconstruction(self.result, self.sources)
        self.assertTrue(any("got 0" in e for e in errors))
        self.assertTrue(any("got 2" in e for e in errors))

    def test_grid_holes_and_fabricated_coordinates_are_rejected(self):
        self.result.tables[0].n_cols = 2
        self.result.tables[0].cells[0].regions[0].bbox = [70, 40, 90, 60]
        errors, _ = validate_reconstruction(self.result, self.sources)
        self.assertTrue(any("uncovered" in e for e in errors))
        self.assertTrue(any("outside its assigned geometry" in e for e in errors))

    def test_math_and_numeric_literal_validation(self):
        cell = self.result.tables[0].cells[0]
        cell.kind, cell.text = "math", r"$\varphi"
        self.assertTrue(any("unpaired" in e for e in validate_reconstruction(self.result, self.sources)[0]))
        self.sources[0]["text_blocks"][0]["text"] = "1,05"
        cell.kind, cell.text, cell.num = "number", "1,05", 1.5
        self.assertTrue(any("num differs" in e for e in validate_reconstruction(self.result, self.sources)[0]))
        cell.num = 1.05
        self.assertEqual(validate_reconstruction(self.result, self.sources)[0], [])

    def test_unassigned_blocks_require_review(self):
        value = self.result.model_dump()
        value["tables"][0]["cells"][0]["blocks"] = []
        value["unassigned_blocks"] = [{"id": "a:b0", "reason": "alignment is ambiguous"}]
        errors, warnings = validate_reconstruction(TableReconstruction.model_validate(value), self.sources)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_unknown_figure_file_and_crop_outside_cell_rejected(self):
        value = self.result.model_dump()
        cell = value["tables"][0]["cells"][0]
        cell["figures"] = [{"region_id": "a", "page": 1, "bbox": [0, 30, 20, 50], "src": "../outside.png"}]
        errors, _ = validate_reconstruction(TableReconstruction.model_validate(value), self.sources)
        self.assertTrue(any("filename" in e for e in errors))
        self.assertTrue(any("figure crop outside cell" in e for e in errors))

    def test_figures_are_saved_from_the_source_and_html_is_escaped(self):
        table = self.result.tables[0]
        value = table.model_dump()
        value["cells"][0]["text"] = '<script>bad</script> $\\varphi$'
        value["cells"][0]["figures"] = [{"region_id": "a", "page": 1, "bbox": [30, 0, 50, 20]}]
        table = type(table).model_validate(value)
        block = Table(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0, block_id=0)
        html, images, exported = render_table(table, {"a": Image.new("RGB", (100, 100), "red")}, block)
        self.assertNotIn("<script>", html)
        self.assertIn(r"<math>\varphi</math>", html)
        self.assertEqual(next(iter(images.values())).getpixel((0, 0)), (255, 0, 0))
        self.assertIsNotNone(exported["cells"][0]["figures"][0]["src"])


class WindowTests(unittest.TestCase):
    def test_table_number_suffix_is_preserved(self):
        self.assertEqual(CAPTION.match("Таблица 10а")[1], "10а")
        self.assertNotEqual(CAPTION.match("Таблица 10")[1], CAPTION.match("Таблица 10а")[1])

    def test_three_page_table_has_no_duplicate_overlap_rows(self):
        a, b, c = geometry("a", 1), geometry("b", 2, "Б"), geometry("c", 3, "В")
        merged = stitch_tables(reconstruction([a, b]).tables[0], reconstruction([b, c]).tables[0])
        output = TableReconstruction(schema_version="1.1", tables=[merged], unassigned_blocks=[], warnings=[])
        self.assertEqual(merged.n_rows, 3)
        self.assertEqual([cell.text for cell in merged.cells], ["А", "Б", "В"])
        self.assertEqual(validate_reconstruction(output, [a, b, c]), ([], []))

    def test_disagreement_in_overlap_is_not_silently_merged(self):
        a, b, c = geometry("a", 1), geometry("b", 2), geometry("c", 3)
        right = reconstruction([b, c]).tables[0]
        right.cells[0].text = "wrong"
        with self.assertRaisesRegex(ValueError, "disagree"):
            stitch_tables(reconstruction([a, b]).tables[0], right)

    def test_processor_retries_without_changing_original_on_failure(self):
        g = geometry("/page/0/Table/0", 1)
        block = Table(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0, block_id=0,
                      table_geometry=g, html="<table><tr><td>original</td></tr></table>")
        page = PageGroup(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0,
                         children=[block], structure=[block.id], highres_image=Image.new("RGB", (100, 100)))
        document = Document(filepath="scan.png", pages=[page])
        model = Mock(return_value={"invalid": True})
        processor = LLMTableJSONProcessor(model, {"use_llm": True, "table_json_reconstruction": True})
        processor(document)
        self.assertEqual(model.call_count, 3)
        self.assertIn("original", block.html)
        self.assertEqual(block.table_json_report["status"], "rejected")

    def test_processor_accepts_valid_json_and_protects_source_grid(self):
        block = Table(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0, block_id=0, html="old")
        g = geometry(str(block.id), 1)
        block.table_geometry = g
        page = PageGroup(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0,
                         children=[block], structure=[block.id], highres_image=Image.new("RGB", (100, 100)))
        document = Document(filepath="scan.png", pages=[page])
        processor = LLMTableJSONProcessor(Mock(return_value=reconstruction([g]).model_dump()),
                                          {"use_llm": True, "table_json_reconstruction": True})
        processor(document)
        self.assertIsNotNone(block.table_json)
        self.assertEqual(block.table_json_report["status"], "structurally_valid")

    def test_three_page_processor_publishes_one_table_and_all_provenance(self):
        pages, blocks, sources = [], [], []
        for i, text in enumerate(["А", "Б", "В"]):
            block = Table(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=i, block_id=0, html="old")
            g = geometry(str(block.id), i + 1, text)
            block.table_geometry = g
            blocks.append(block)
            sources.append(g)
            pages.append(PageGroup(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=i,
                                   children=[block], structure=[block.id], highres_image=Image.new("RGB", (100, 100))))
        document = Document(filepath="scan.png", pages=pages)
        model = Mock(side_effect=[reconstruction(sources[:2]).model_dump(), reconstruction(sources[1:]).model_dump()])
        LLMTableJSONProcessor(model, {"use_llm": True, "table_json_reconstruction": True})(document)
        self.assertEqual(blocks[0].table_json["n_rows"], 3)
        self.assertTrue(all(b.ignore_for_output for b in blocks[1:]))
        archive = MarkdownRenderer({"table_json_reconstruction": True})(document).metadata["table_reconstruction"]
        self.assertEqual(len(archive["reconstruction"]["tables"]), 1)
        self.assertEqual(len(archive["sources"]), 3)


class ExportTests(unittest.TestCase):
    def test_markdown_json_and_table_archive_are_written(self):
        block = Table(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0, block_id=0, html="old")
        g = geometry(str(block.id), 1)
        block.table_geometry = g
        page = PageGroup(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0, children=[block],
                         structure=[block.id], highres_image=Image.new("RGB", (100, 100)))
        document = Document(filepath="scan.png", pages=[page])
        LLMTableJSONProcessor(Mock(return_value=reconstruction([g]).model_dump()),
                              {"use_llm": True, "table_json_reconstruction": True})(document)
        with tempfile.TemporaryDirectory() as output:
            rendered = MarkdownRenderer({"table_json_reconstruction": True})(document)
            save_output(rendered, output, "document")
            self.assertIn("<table>", Path(output, "document.md").read_text())
            archive = json.loads(Path(output, "document_tables.json").read_text())
            self.assertEqual(archive["validation"][0]["status"], "structurally_valid")
            TableReconstruction.model_validate(archive["reconstruction"])
            rendered_json = JSONRenderer({"table_json_reconstruction": True})(document)
            save_output(rendered_json, output, "document_json")
            payload = json.loads(Path(output, "document_json.json").read_text())
            self.assertIsNotNone(payload["children"][0]["children"][0]["table_json"])

    def test_no_tables_still_exports_empty_archive(self):
        page = PageGroup(polygon=PolygonBox.from_bbox([0, 0, 100, 100]), page_id=0, children=[], structure=[])
        document = Document(filepath="empty.pdf", pages=[page])
        archive = MarkdownRenderer({"table_json_reconstruction": True})(document).metadata["table_reconstruction"]
        self.assertEqual(archive["reconstruction"]["tables"], [])
        self.assertEqual(archive["validation"], [])


class CloudServiceTests(unittest.TestCase):
    def test_cloud_omits_unsupported_response_format_and_validates_json_locally(self):
        class Reply(BaseModel):
            value: str

        service = OpenAIService({"openai_api_key": "offline-placeholder", "openai_base_url": "https://ollama.com/v1"})
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"value":"ok"}'), finish_reason="stop")], usage=None)
        service.get_client = Mock(return_value=client)
        self.assertEqual(service("reconstruct", None, None, Reply), {"value": "ok"})
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["temperature"], 0)
        self.assertNotIn("response_format", kwargs)
        self.assertIn('"properties"', kwargs["messages"][0]["content"][0]["text"])
        client.chat.completions.parse.assert_not_called()


if __name__ == "__main__":
    unittest.main()
