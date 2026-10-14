"""Check structure and provenance; this does not prove engineering correctness."""

import re
from collections import Counter

from marker.tables.schema import TableReconstruction


def inside(inner, outer, tolerance=2):
    return (outer[0] - tolerance <= inner[0] < inner[2] <= outer[2] + tolerance
            and outer[1] - tolerance <= inner[1] < inner[3] <= outer[3] + tolerance)


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def balanced_math(text):
    # Escaped currency dollars are not formula delimiters.
    return len(re.findall(r"(?<!\\)(?:\\\\)*\$", text)) % 2 == 0


def normalized_text(text, dehyphenated=False):
    text = re.sub(r"\s+", "", text).replace("\u00ad", "")
    return text.replace("-", "") if dehyphenated else text


def validate_reconstruction(result: TableReconstruction, geometry: list[dict]):
    errors, warnings = [], list(result.warnings)
    sources = {g["region"]["region_id"]: g["region"] for g in geometry}
    source_blocks = {b["id"]: b for g in geometry for b in g["text_blocks"]}
    used, region_uses = Counter(), Counter()

    def check_regions(regions, where):
        for region in regions:
            source = sources.get(region.region_id)
            if source is None or region.page != source["page"]:
                errors.append(f"{where}: unknown region/page {region.region_id}")
            elif not inside(region.bbox, source["bbox"], tolerance=0):
                errors.append(f"{where}: bbox outside source {region.region_id}")

    def check_blocks(ids, regions, where):
        used.update(ids)
        for block_id in ids:
            block = source_blocks.get(block_id)
            if block is None:
                errors.append(f"{where}: unknown block {block_id}")
            elif not any(region.region_id == block["region_id"]
                         and intersects(region.bbox, block["bbox"]) for region in regions):
                errors.append(f"{where}: block {block_id} outside its assigned geometry")

    for ti, table in enumerate(result.tables):
        name = f"table[{ti}]"
        warnings.extend(table.warnings)
        check_regions(table.regions, name)
        for region in table.regions:
            region_uses[region.region_id] += 1
            source = sources.get(region.region_id)
            if source and region.bbox != source["bbox"]:
                errors.append(f"{name}: region must retain the full input crop")
        if sorted(set(table.pages)) != sorted({r.page for r in table.regions}):
            errors.append(f"{name}: pages do not match regions")
        if table.header_rows > table.n_rows:
            errors.append(f"{name}: header_rows exceeds n_rows")
        if table.n_rows * table.n_cols > 100000:
            errors.append(f"{name}: grid exceeds validation limit")
            continue
        if bool(table.n_rows) != bool(table.n_cols):
            errors.append(f"{name}: both grid dimensions must be zero or positive")
        grid = {}
        owned_regions = {t.region_id for t in table.regions}
        check_regions(table.column_regions, name + ".column_regions")
        check_regions(table.row_regions, name + ".row_regions")
        for regions, key, limit in ((table.column_regions, "c", table.n_cols),
                                    (table.row_regions, "r", table.n_rows)):
            if set(getattr(r, key) for r in regions) != set(range(limit)):
                errors.append(f"{name}: {key} regions must locate every logical {key}")
            for region in regions:
                if region.region_id not in owned_regions:
                    errors.append(f"{name}: {key} region references another table")
            for i, a in enumerate(regions):
                for b in regions[i + 1:]:
                    if a.region_id != b.region_id or getattr(a, key) == getattr(b, key):
                        continue
                    start, end = (0, 2) if key == "c" else (1, 3)
                    if min(a.bbox[end], b.bbox[end]) - max(a.bbox[start], b.bbox[start]) > 2:
                        errors.append(f"{name}: physical {key} bands overlap")
                    if getattr(a, key) < getattr(b, key) and a.bbox[start] > b.bbox[start] + 2:
                        errors.append(f"{name}: physical {key} order contradicts grid")
                    if getattr(a, key) > getattr(b, key) and a.bbox[start] + 2 < b.bbox[start]:
                        errors.append(f"{name}: physical {key} order contradicts grid")
        for ci, cell in enumerate(table.cells):
            where = f"{name}.cell[{ci}]"
            check_regions(cell.regions, where)
            if cell.kind != "empty" and not cell.regions:
                errors.append(f"{where}: nonempty cell has no geometry")
            check_blocks(cell.blocks, cell.regions, where)
            if any(r.region_id not in owned_regions for r in cell.regions):
                errors.append(f"{where}: cell references another table")
            if cell.r + cell.rowspan > table.n_rows or cell.c + cell.colspan > table.n_cols:
                errors.append(f"{where}: span outside grid")
                continue
            for region in cell.regions:
                rows = [rr for rr in table.row_regions if rr.region_id == region.region_id
                        and cell.r <= rr.r < cell.r + cell.rowspan]
                cols = [cc for cc in table.column_regions if cc.region_id == region.region_id
                        and cell.c <= cc.c < cell.c + cell.colspan]
                if not rows or not cols:
                    errors.append(f"{where}: cell has no matching physical row/column bands")
                elif not inside(region.bbox, [min(c.bbox[0] for c in cols), min(r.bbox[1] for r in rows),
                                              max(c.bbox[2] for c in cols), max(r.bbox[3] for r in rows)]):
                    errors.append(f"{where}: cell bbox contradicts its logical row/column")
            for r in range(cell.r, cell.r + cell.rowspan):
                for c in range(cell.c, cell.c + cell.colspan):
                    if (r, c) in grid:
                        errors.append(f"{where}: span intersection at {r},{c}")
                    grid[r, c] = ci
            if not balanced_math(cell.text):
                errors.append(f"{where}: unpaired math delimiters")
            if cell.role == "header" and cell.r >= table.header_rows:
                errors.append(f"{where}: header outside header_rows")
            if cell.kind == "empty" and (cell.text or cell.blocks or cell.figures):
                errors.append(f"{where}: empty cell contains content")
            if cell.kind == "figure" and not cell.figures:
                errors.append(f"{where}: figure cell has no source crop")
            if cell.kind == "number":
                try:
                    value = float(cell.text.strip().replace("\u2212", "-").replace(",", "."))
                    if cell.num is None or value != cell.num:
                        raise ValueError()
                except ValueError:
                    errors.append(f"{where}: num differs from literal text")
            if cell.kind in ("text", "number", "dash"):
                target = normalized_text(cell.text, "dehyphenated" in cell.flags)
                for block_id in cell.blocks:
                    block = source_blocks.get(block_id, {})
                    if block.get("type") != "text" or not block.get("text"):
                        continue
                    source_text = normalized_text(block["text"], "dehyphenated" in cell.flags)
                    if source_text not in target and "text_mismatch" not in cell.flags:
                        errors.append(f"{where}: source text changed without text_mismatch")
            if set(cell.flags) & {"unreadable", "ambiguous_alignment", "text_mismatch"}:
                warnings.append(f"{where}: requires content review")
            for figure in cell.figures:
                if figure.src is not None:
                    errors.append(f"{where}: model must not supply a figure filename")
                if figure.bbox[2] - figure.bbox[0] < 1 or figure.bbox[3] - figure.bbox[1] < 1:
                    errors.append(f"{where}: figure crop is smaller than a pixel")
                check_regions([figure], where + ".figure")
                if not any(r.region_id == figure.region_id and inside(figure.bbox, r.bbox)
                           for r in cell.regions):
                    errors.append(f"{where}: figure crop outside cell")
        missing = table.n_rows * table.n_cols - len(grid)
        if missing:
            errors.append(f"{name}: {missing} grid positions uncovered")
        check_blocks(table.caption_blocks + table.amendment_blocks, table.regions, name)
        for note in table.notes:
            check_regions(note.regions, name + ".note")
            check_blocks(note.blocks, note.regions, name + ".note")
            if any(r.region_id not in owned_regions for r in note.regions):
                errors.append(f"{name}: note references another table")
            if not balanced_math(note.text):
                errors.append(f"{name}: unpaired math in note")

    for block in result.unassigned_blocks:
        if block.id not in source_blocks:
            errors.append(f"unknown unassigned block {block.id}")
        used[block.id] += 1
        warnings.append(f"unassigned block {block.id}: {block.reason}")
    for block_id in source_blocks:
        if used[block_id] != 1:
            errors.append(f"block {block_id}: expected one assignment, got {used[block_id]}")
    for region_id in sources:
        if region_uses[region_id] != 1:
            errors.append(f"region {region_id}: expected one table, got {region_uses[region_id]}")
    for g in geometry:
        warnings.extend(g.get("warnings", []))
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))
