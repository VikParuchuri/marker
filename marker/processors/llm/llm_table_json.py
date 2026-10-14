"""Geometry -> LLM JSON -> deterministic validation -> HTML and JSON exports."""

import json
from pathlib import Path
from typing import Annotated

from pydantic import ValidationError

from marker.logger import get_logger
from marker.processors.llm import BaseLLMProcessor
from marker.schema import BlockTypes
from marker.tables.geometry import CAPTION, crop_table
from marker.tables.render import render_table
from marker.tables.schema import TableReconstruction
from marker.tables.stitch import stitch_tables
from marker.tables.validation import validate_reconstruction

logger = get_logger()
TABLE_PROMPT = (Path(__file__).parents[2] / "tables" / "russian_normative.md").read_text(encoding="utf-8")


class LLMTableJSONProcessor(BaseLLMProcessor):
    table_json_reconstruction: Annotated[bool, "Reconstruct tables as geometry-backed validated JSON."] = False
    table_json_retries: Annotated[int, "Retries after JSON/schema/geometric validation failures."] = 2
    table_json_max_blocks: Annotated[int, "Maximum source blocks per two-page table window."] = 4000
    extract_images: Annotated[bool, "Save figures from reconstructed table cells."] = True
    block_types = (BlockTypes.Table,)

    def __call__(self, document):
        if not self.table_json_reconstruction or not self.use_llm or self.llm_service is None:
            return
        blocks = [b for page in document.pages for b in page.contained_blocks(document, self.block_types)
                  if not b.ignore_for_output]
        runs = []
        for block in blocks:
            if runs and self.candidate_continuation(document, runs[-1][-1], block):
                runs[-1].append(block)
            else:
                runs.append([block])
        for run in runs:
            try:
                self.reconstruct_run(document, run)
            except Exception as error:
                logger.exception("Table JSON reconstruction failed for %s", run[0].id)
                run[0].table_json_report = {"status": "rejected", "errors": [type(error).__name__],
                                            "regions": [str(b.id) for b in run]}
                run[0].update_metadata(llm_error_count=1)

    @staticmethod
    def candidate_continuation(document, previous, current):
        if current.page_id != previous.page_id + 1:
            return False
        old = (previous.table_geometry or {}).get("caption_hint", "")
        new = (current.table_geometry or {}).get("caption_hint", "")
        old_num, new_num = CAPTION.match(old), CAPTION.match(new)
        if new_num and (not old_num or new_num[1] != old_num[1]):
            return False
        a, b = document.get_page(previous.page_id), document.get_page(current.page_id)
        ax0, ax1 = previous.polygon.x_start / a.polygon.width, previous.polygon.x_end / a.polygon.width
        bx0, bx1 = current.polygon.x_start / b.polygon.width, current.polygon.x_end / b.polygon.width
        return min(ax1, bx1) - max(ax0, bx0) >= min(ax1 - ax0, bx1 - bx0) * 0.75

    def reconstruct_window(self, geometry, images, block, previous_tables):
        if sum(len(g["text_blocks"]) for g in geometry) > self.table_json_max_blocks:
            return None, ["window exceeds table_json_max_blocks; no source blocks were discarded"], [], None
        payload = {"regions": [dict(g["region"], caption_hint=g["caption_hint"]) for g in geometry],
                   "text_blocks": [b for g in geometry for b in g["text_blocks"]],
                   "rules": [dict(rule, region_id=g["region"]["region_id"], page=g["region"]["page"])
                             for g in geometry for rule in g["rules"]],
                   "previous_tables": [{"number": t.number, "title": t.title, "pages": t.pages} for t in previous_tables]}
        prompt = TABLE_PROMPT + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False)
        errors, warnings, response = [], [], None
        for _ in range(max(0, self.table_json_retries) + 1):
            response = self.llm_service(prompt, images, block, TableReconstruction)
            try:
                result = TableReconstruction.model_validate(response)
                errors, warnings = validate_reconstruction(result, geometry)
                if not errors:
                    return result, [], warnings, response
            except ValidationError as error:
                errors = [f'{e["loc"]}: {e["msg"]}' for e in error.errors(include_input=False)]
            prompt = (TABLE_PROMPT + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False)
                      + "\n\nПредыдущий ответ отклонён. Исправь перечисленные нарушения, сохрани все исходные данные:\n"
                      + json.dumps(errors[:30], ensure_ascii=False))
        return None, errors, warnings, response

    def reconstruct_run(self, document, run):
        owner = run[0]
        geometry = [b.table_geometry for b in run]
        if any(g is None for g in geometry):
            owner.table_json_report = {"status": "rejected", "errors": ["source geometry unavailable"],
                                       "regions": [str(b.id) for b in run]}
            return
        images = {str(b.id): crop_table(document.get_page(b.page_id), b)[0] for b in run}
        records, warnings = [], []
        windows = [run] if len(run) == 1 else [run[i:i + 2] for i in range(len(run) - 1)]
        for window in windows:
            result, errors, found_warnings, response = self.reconstruct_window(
                [b.table_geometry for b in window], [images[str(b.id)] for b in window], window[0], records)
            warnings.extend(found_warnings)
            if result is None:
                owner.table_json_report = {"status": "rejected", "errors": errors, "warnings": warnings,
                                           "regions": [str(b.id) for b in run], "rejected_response": response}
                owner.update_metadata(llm_error_count=1)
                return
            if found_warnings or result.unassigned_blocks:
                owner.table_json_report = {"status": "needs_review", "errors": [], "warnings": warnings,
                                           "regions": [str(b.id) for b in run], "candidate": result.model_dump()}
                return
            for table in result.tables:
                ids = {r.region_id for r in table.regions}
                matches = [i for i, old in enumerate(records) if ids & {r.region_id for r in old.regions}]
                if len(matches) > 1:
                    errors = ["window changes previously separated table boundaries"]
                elif matches:
                    try:
                        records[matches[0]] = stitch_tables(records[matches[0]], table)
                    except ValueError as error:
                        errors = [str(error)]
                else:
                    records.append(table)
                if errors:
                    owner.table_json_report = {"status": "needs_review", "errors": errors, "warnings": warnings,
                                               "regions": [str(b.id) for b in run], "candidate": result.model_dump()}
                    return
        candidate = TableReconstruction(schema_version="1.1", tables=records, unassigned_blocks=[], warnings=[])
        errors, final_warnings = validate_reconstruction(candidate, geometry)
        warnings = list(dict.fromkeys(warnings + final_warnings))
        report = {"status": "structurally_valid", "errors": errors, "warnings": warnings,
                  "regions": [str(b.id) for b in run]}
        if errors or warnings:
            report["status"] = "rejected" if errors else "needs_review"
            report["candidate"] = candidate.model_dump()
            owner.table_json_report = report
            return
        # Prepare all output before mutating any original table in the run.
        by_id = {str(b.id): b for b in run}
        rendered = []
        for table in records:
            target = by_id[table.regions[0].region_id]
            html, embedded, exported = render_table(table, images, target, self.extract_images)
            rendered.append((target, html, embedded, exported))
        for block in run:
            block.html = None
            block.structure = []
            block.ignore_for_output = True
        for target, html, embedded, exported in rendered:
            target.html = html
            target.embedded_images = embedded
            target.table_json = exported
            target.ignore_for_output = False
        owner.table_json_report = report
