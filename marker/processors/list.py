from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class ListProcessor(BaseProcessor):
    """
    A processor for merging lists across pages and columns
    """
    block_types = (BlockTypes.ListGroup,)
    ignored_block_types = (BlockTypes.PageHeader, BlockTypes.PageFooter)
    min_x_indent = 0.05  # % of block width
    x_start_tolerance = 0.01  # % of block width
    x_end_tolerance = 0.01  # % of block width

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        self.list_group_continuation(document)
        self.list_group_indentation(document)

    def list_group_continuation(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                next_block = document.get_next_block(block, self.ignored_block_types)
                if next_block is None:
                    continue
                if next_block.block_type not in self.block_types:
                    continue
                if next_block.structure is None:
                    continue
                if next_block.ignore_for_output:
                    continue

                column_break, page_break = False, False
                next_block_in_first_quadrant = False

                if next_block.page_id == block.page_id:  # block on the same page
                    # we check for a column break
                    column_break = next_block.polygon.y_start <= block.polygon.y_end
                else:
                    page_break = True
                    next_page = document.get_page(next_block.page_id)
                    next_block_in_first_quadrant = (next_block.polygon.x_start < next_page.polygon.width // 2) and \
                        (next_block.polygon.y_start < next_page.polygon.height // 2)

                block.has_continuation = column_break or (page_break and next_block_in_first_quadrant)

    def list_group_indentation(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if block.structure is None:
                    continue
                if block.ignore_for_output:
                    continue

                for list_item_id in block.structure:
                    list_item_block = page.get_block(list_item_id)

                    next_list_item_block = block.get_next_block(page, list_item_block)
                    if next_list_item_block is None:
                        break
                    if next_list_item_block.structure is None:
                        break

                    matching_x_end = abs(next_list_item_block.polygon.x_end - list_item_block.polygon.x_end) < self.x_end_tolerance * list_item_block.polygon.width
                    matching_x_start = abs(next_list_item_block.polygon.x_start - list_item_block.polygon.x_start) < self.x_start_tolerance * list_item_block.polygon.width
                    x_indent = next_list_item_block.polygon.x_start > list_item_block.polygon.x_start + (self.min_x_indent * list_item_block.polygon.width)
                    y_indent = next_list_item_block.polygon.y_start > list_item_block.polygon.y_start

                    if list_item_block.list_indent_level and (matching_x_end and matching_x_start) or (x_indent and y_indent):
                        next_list_item_block.list_indent_level = list_item_block.list_indent_level
                        if (x_indent and y_indent):
                            next_list_item_block.list_indent_level += 1
                    elif (x_indent and y_indent):
                        next_list_item_block.list_indent_level = 1

                    list_item_block = next_list_item_block

                for list_item_id in reversed(block.structure):
                    list_item_block = page.get_block(list_item_id)
                    prev_list_item_block = block.get_prev_block(page, list_item_block)
                    if prev_list_item_block is None:
                        break
                    if prev_list_item_block.structure is None:
                        break

                    if list_item_block.list_indent_level > prev_list_item_block.list_indent_level:
                        prev_list_item_block.add_structure(list_item_block)
                        prev_list_item_block.polygon = prev_list_item_block.polygon.merge([list_item_block.polygon])
                        block.remove_structure_items([list_item_id])
