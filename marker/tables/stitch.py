"""Join overlapping windows only when their source-backed rows agree."""

from collections import Counter

from marker.tables.schema import Table
from marker.tables.validation import normalized_text


def unique(items):
    found = set()
    result = []
    for item in items:
        key = item.model_dump_json() if hasattr(item, "model_dump_json") else item
        if key not in found:
            found.add(key)
            result.append(item)
    return result


def stitch_tables(left: Table, right: Table) -> Table:
    shared = {r.region_id for r in left.regions} & {r.region_id for r in right.regions}
    if not shared:
        raise ValueError("windows do not have a shared source region")
    if left.number and right.number and left.number != right.number:
        raise ValueError("different table numbers")
    if left.n_cols != right.n_cols:
        raise ValueError("different column counts in overlapping windows")
    old_owners = {b: cell for cell in left.cells for b in cell.blocks}
    offsets = Counter()
    for cell in right.cells:
        if cell.rowspan != 1 or cell.role == "header":
            continue
        for bid in cell.blocks:
            old = old_owners.get(bid)
            if old and old.rowspan == 1 and old.c == cell.c and old.colspan == cell.colspan:
                offsets[old.r - cell.r] += 1
    if not offsets:
        # Empty cells may not have block ids; use explicit row geometry.
        for new in right.row_regions:
            for old in left.row_regions:
                if new.region_id == old.region_id and new.bbox == old.bbox:
                    offsets[old.r - new.r] += 1
    if len(offsets) != 1:
        raise ValueError("overlap does not establish one unambiguous row offset")
    offset = next(iter(offsets))
    if offset < 0:
        raise ValueError("overlap would move new rows before the existing table")
    merged = left.model_copy(deep=True)
    header_left = [(c.r, c.c, c.rowspan, c.colspan, normalized_text(c.text)) for c in left.cells if c.role == "header"]
    header_right = [(c.r, c.c, c.rowspan, c.colspan, normalized_text(c.text)) for c in right.cells if c.role == "header"]
    repeated_header = bool(offset and header_left and sorted(header_left) == sorted(header_right))

    def mapped_row(r):
        return r if repeated_header and r < right.header_rows else r + offset

    for source in right.cells:
        cell = source.model_copy(deep=True)
        cell.r = mapped_row(cell.r)
        overlaps = [old for old in merged.cells
                    if max(old.r, cell.r) < min(old.r + old.rowspan, cell.r + cell.rowspan)
                    and max(old.c, cell.c) < min(old.c + old.colspan, cell.c + cell.colspan)]
        if not overlaps:
            merged.cells.append(cell)
            continue
        if len(overlaps) != 1:
            raise ValueError("overlap changes cell segmentation")
        old = overlaps[0]
        if (old.c != cell.c or old.colspan != cell.colspan or old.kind != cell.kind
                or old.role != cell.role or normalized_text(old.text) != normalized_text(cell.text)):
            raise ValueError("overlapping cell content or columns disagree")
        if old.r != cell.r and not (set(old.blocks) & set(cell.blocks)):
            raise ValueError("rowspan extension has no shared source evidence")
        end = max(old.r + old.rowspan, cell.r + cell.rowspan)
        old.r = min(old.r, cell.r)
        old.rowspan = end - old.r
        old.blocks = unique(old.blocks + cell.blocks)
        old.regions = unique(old.regions + cell.regions)
        for figure in cell.figures:
            matches = [f for f in old.figures if (f.region_id, f.page, f.bbox) ==
                       (figure.region_id, figure.page, figure.bbox)]
            if matches:
                matches[0].labels = unique(matches[0].labels + figure.labels)
            else:
                old.figures.append(figure)
        old.flags = unique(old.flags + cell.flags)
    for note in right.notes:
        matches = [n for n in merged.notes if set(n.blocks) & set(note.blocks)]
        if matches:
            if len(matches) != 1 or normalized_text(matches[0].text) != normalized_text(note.text):
                raise ValueError("overlapping note content disagrees")
            matches[0].blocks = unique(matches[0].blocks + note.blocks)
            matches[0].regions = unique(matches[0].regions + note.regions)
        else:
            merged.notes.append(note.model_copy(deep=True))
    merged.regions = unique(merged.regions + right.regions)
    merged.row_regions = unique(merged.row_regions + [r.model_copy(update={"r": mapped_row(r.r)}) for r in right.row_regions])
    merged.column_regions = unique(merged.column_regions + right.column_regions)
    merged.n_rows = max(merged.n_rows, right.n_rows + offset)
    merged.pages = sorted(set(merged.pages + right.pages))
    merged.caption_blocks = unique(merged.caption_blocks + right.caption_blocks)
    merged.amendment_blocks = unique(merged.amendment_blocks + right.amendment_blocks)
    merged.number = merged.number or right.number
    merged.title = merged.title or right.title
    merged.amendment_note = merged.amendment_note or right.amendment_note
    merged.truncated_end = right.truncated_end
    merged.warnings = unique(merged.warnings + right.warnings)
    return merged
