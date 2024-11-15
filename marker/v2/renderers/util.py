def renderer_for_block(block, renderer_list: list):
    from marker.v2.renderers.default import DefaultRenderer

    for renderer in renderer_list:
        if renderer.block_type == block.block_type:
            return renderer

    return DefaultRenderer()
