from copy import deepcopy
from typing import Annotated

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import BlockId
from marker.schema.document import Document
from marker.schema.registry import get_block_class

from marker.logger import get_logger
logger = get_logger()

class BlockRelabelProcessor(BaseProcessor):
    """
    A processor to heuristically relabel blocks based on a confidence threshold.
    
    Each rule in the relabel string maps an original block label to a new one
    if the confidence exceeds a given threshold.
    """
    
    block_relabel_str: Annotated[
        str,
        "Comma-separated relabeling rules in the format '<original_label>:<new_label>:<confidence_threshold>'.",
        "Each rule defines how blocks of a certain type should be relabeled when the confidence exceeds the threshold.",
        "Example: 'Table:Picture:0.85,Form:Picture:0.9'"
    ] = ""
    block_relabel_str: str = ""
    def __init__(self, config = None):
        super().__init__(config)
        
        self.block_relabel_map = {}
        for block_config_str in self.block_relabel_str.split(','):
            block_config_str = block_config_str.strip()
            block_label, block_relabel, confidence_thresh = block_config_str.split(':')
            confidence_thresh = float(confidence_thresh)
            self.block_relabel_map[BlockTypes[block_label]] = (confidence_thresh, BlockTypes[block_relabel])

    def __call__(self, document: Document):
        if len(self.block_relabel_map) == 0:
            return

        for page in document.pages:
            for block in page.structure_blocks(document):
                if block.block_type not in self.block_relabel_map:
                    continue
                
                block_id = BlockId(page_id=page.page_id, block_id=block.block_id, block_type=block.block_type)
                confidence_thresh, relabel_block_type = self.block_relabel_map[block.block_type]
                confidence = block.top_k.get(block.block_type)
                if confidence > confidence_thresh:
                    logger.debug(f"Skipping relabel for {block_id}; Confidence: {confidence} > Confidence Threshold {confidence_thresh} for re-labelling")
                    continue

                new_block_cls = get_block_class(relabel_block_type)
                new_block = new_block_cls(
                    polygon=deepcopy(block.polygon),
                    page_id=block.page_id,
                    structure=deepcopy(block.structure),
                    text_extraction_method=block.text_extraction_method,
                    source="heuristics",
                    top_k=block.top_k,
                    metadata=block.metadata
                )
                page.replace_block(block, new_block)
                logger.debug(f"Relabelled {block_id} to {relabel_block_type}")