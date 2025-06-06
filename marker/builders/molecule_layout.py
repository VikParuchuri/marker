from typing import Annotated, List, Dict, Any, Optional
import random

from marker.builders import BaseBuilder
from marker.providers.pdf import PdfProvider
from marker.schema.document import Document
from marker.schema.groups import PageGroup
from marker.schema.blocks import Molecule, MoleculeTable
from marker.schema.polygon import PolygonBox
from marker.schema import BlockTypes

import copy
import sys
import traceback
from PIL import Image
from tqdm import tqdm
import os
import warnings
import io

# Try to import img2mol processor
try:
    sys.path.append('/app/img2mol')
    from img2mol.processor import Parser_Processer
    IMG2MOL_AVAILABLE = True
except ImportError:
    print("Warning: img2mol.processor not found. Using mock mode.")
    IMG2MOL_AVAILABLE = False

# Suppress warnings
warnings.filterwarnings("ignore")


class MoleculeLayoutBuilder(BaseBuilder):
    """
    A builder for performing chemical molecule layout detection on PDF pages and merging the results into the document.
    Uses img2mol's Parser_Processer for molecule and table detection, or mock data for testing.
    """
    # The overlap threshold for replacing existing blocks with molecule blocks
    overlap_threshold: float = 0.9
    
    # The overlap threshold for replacing table blocks with molecule table blocks  
    table_overlap_threshold: float = 0.9
    
    # Whether to disable the tqdm progress bar
    disable_tqdm: bool = False
    
    # Whether to use mock data instead of real img2mol detection
    use_mock_data: bool = False
    
    def __init__(self, processor_config=None, config=None):
        """
        初始化分子识别Layout Builder
        
        Args:
            processor_config: img2mol Parser_Processer的配置参数
            config: marker配置
        """
        super().__init__(config)
        
        self.processor_config = processor_config or {}
        self.processor = None
        
        # 检查是否使用mock模式
        self.use_mock_data = (
            self.processor_config.get('use_mock_data', False) or 
            not IMG2MOL_AVAILABLE or
            self.processor_config.get('mock_mode', False)
        )
        
        if not self.use_mock_data:
            self._initialize_processor()
        else:
            print("🎭 使用Mock模式进行分子检测测试")
    
    def _initialize_processor(self):
        """Initialize the img2mol Parser_Processer"""
        try:
            # Import img2mol processor
            import sys
            sys.path.append('/app/img2mol')
            from img2mol.processor import Parser_Processer
            
            # Create processor with configuration
            self.processor = Parser_Processer(**self.processor_config)
            
            # Initialize required models
            if self.processor_config.get('with_mol_detect', True):
                self.processor.mol_detection_model = self.processor.get_MolDetect_mol(
                    MolDetect_mol_path=self.processor_config.get('MolDetect_mol_path'),
                    device=self.processor_config.get('device', 'cpu'),
                    input_size=self.processor_config.get('input_size', 1000),
                    coref=self.processor_config.get('coref', True),
                    new_class_token=self.processor_config.get('new_class_token', True)
                )
            
            if self.processor_config.get('with_table_detect', True):
                device = self.processor_config.get('device', 'cpu')
                self.processor.table_detector = self.processor.get_table_detector(device)
                
        except Exception as e:
            print(f"Warning: Failed to initialize img2mol processor: {e}")
            print("🎭 切换到Mock模式")
            self.use_mock_data = True
            self.processor = None

    def __call__(self, document: Document, provider: PdfProvider):
        """Process all pages in the document to detect molecules and tables"""
        if self.use_mock_data:
            detection_results = self.generate_mock_detection_results(document.pages)
        else:
            if self.processor is None:
                print("Molecule processor not available, skipping molecule detection")
                return
            detection_results = self.detect_molecules_and_tables(document.pages)
        
        self.merge_molecule_blocks_to_pages(document.pages, detection_results)

    def generate_mock_detection_results(self, pages: List[PageGroup]) -> List[dict]:
        """
        生成Mock检测结果用于测试
        随机生成一些分子结构，基于已有表格生成分子表格（坐标微调用于测试覆盖功能）
        """
        results = []
        
        for page_idx, page in enumerate(tqdm(pages, disable=self.disable_tqdm, desc="Mock分子检测")):
            molecules = []
            tables = []
            
            # 获取页面尺寸（用于生成合理的bbox）
            page_width = 800  # 默认值
            page_height = 1000  # 默认值
            
            if hasattr(page, 'page_image') and page.page_image:
                if hasattr(page.page_image, 'size'):
                    page_width, page_height = page.page_image.size
                elif hasattr(page.page_image, 'shape'):
                    page_height, page_width = page.page_image.shape[:2]
            
            # 随机生成2-4个分子结构
            num_molecules = random.randint(2, 4)
            for _ in range(num_molecules):
                # 生成随机bbox
                x1 = random.randint(50, page_width - 200)
                y1 = random.randint(50, page_height - 200)
                x2 = x1 + random.randint(80, 150)
                y2 = y1 + random.randint(80, 150)
                
                molecules.append({
                    'bbox': [x1, y1, x2, y2],
                    'confidence': random.uniform(0.8, 0.95),
                    'data': {
                        'bbox': [x1, y1, x2, y2],
                        'smiles': 'c1ccccc1',  # 苯环的SMILES
                        'mock': True
                    }
                })
            
            # 只基于已有的Table blocks生成分子表格mock数据（坐标微调，内容替换）
            existing_tables = []
            if hasattr(page, 'children'):
                existing_tables = [b for b in page.children if hasattr(b, 'block_type') and b.block_type == BlockTypes.Table]
            elif hasattr(page, 'blocks'):
                existing_tables = [b for b in page.blocks if b.block_type == BlockTypes.Table]
            
            if existing_tables:
                print(f"📋 页面 {page_idx + 1}: 发现 {len(existing_tables)} 个已有表格，将生成对应的分子表格mock数据")
                
                for table_block in existing_tables:
                    # 获取原始表格的坐标
                    original_bbox = table_block.polygon.bbox
                    x1, y1, x2, y2 = original_bbox
                    
                    # 微调坐标（稍微偏移，确保有足够重叠来触发替换）
                    # 偏移范围：-5到+5像素，确保90%以上重叠
                    offset_x = random.randint(-5, 5)
                    offset_y = random.randint(-5, 5)
                    
                    adjusted_bbox = [
                        x1 + offset_x,
                        y1 + offset_y, 
                        x2 + offset_x,
                        y2 + offset_y
                    ]
                    
                    # 生成HTML格式的分子表格内容
                    mock_html_table = self._generate_mock_molecule_table_html()
                    
                    tables.append({
                        'bbox': adjusted_bbox,
                        'confidence': random.uniform(0.85, 0.95),
                        'data': {
                            'bbox': adjusted_bbox,
                            'original_bbox': original_bbox,  # 保存原始坐标用于调试
                            'table_type': 'molecule_table',
                            'html_content': mock_html_table,
                            'format': 'html',
                            'mock': True,
                            'source': 'existing_table_adjusted'  # 标记数据来源
                        }
                    })
            else:
                print(f"📋 页面 {page_idx + 1}: 未发现已有表格，跳过分子表格生成")
            
            results.append({
                'page_idx': page_idx,
                'molecules': molecules,
                'tables': tables
            })
            
            print(f"📄 页面 {page_idx + 1}: Mock生成 {len(molecules)} 个分子, {len(tables)} 个分子表格 (基于已有表格)")
        
        return results

    def _generate_mock_molecule_table_html(self):
        """
        生成Mock分子表格的HTML内容
        包含化学分子结构数据，cell里填入C1CCCCC1等SMILES
        """
        # 定义一些常见的分子SMILES
        molecules = [
            'C1CCCCC1',      # 环己烷
            'c1ccccc1',      # 苯
            'CCO',           # 乙醇  
            'CC(=O)O',       # 乙酸
            'CC(C)C',        # 异丙烷
            'C1=CC=CC=C1O',  # 苯酚
            'CCN',           # 乙胺
            'C1CCC(CC1)O'    # 环己醇
        ]
        
        # 随机选择表格大小（2-4行，2-3列）
        rows = random.randint(2, 4)
        cols = random.randint(2, 3)
        
        # 构建HTML表格
        html_parts = ['<table border="1" style="border-collapse: collapse;">']
        
        # 表头
        html_parts.append('<tr>')
        headers = ['化合物', 'SMILES', '分子量'] if cols == 3 else ['化合物', 'SMILES']
        for header in headers[:cols]:
            html_parts.append(f'<th style="padding: 8px; background-color: #f0f0f0;">{header}</th>')
        html_parts.append('</tr>')
        
        # 数据行
        for i in range(rows):
            html_parts.append('<tr>')
            mol_smiles = random.choice(molecules)
            
            for j in range(cols):
                if j == 0:  # 化合物名称列
                    content = f'化合物-{i+1}'
                elif j == 1:  # SMILES列
                    content = mol_smiles
                else:  # 分子量列
                    content = f'{random.randint(50, 300)}.{random.randint(10, 99)}'
                
                html_parts.append(f'<td style="padding: 8px; text-align: center;">{content}</td>')
            
            html_parts.append('</tr>')
        
        html_parts.append('</table>')
        
        return ''.join(html_parts)

    def detect_molecules_and_tables(self, pages: List[PageGroup]) -> List[dict]:
        """
        Detect molecules and tables on each page using img2mol
        
        Returns:
            List of detection results for each page
        """
        results = []
        
        for page_idx, page in enumerate(tqdm(pages, disable=self.disable_tqdm, desc="Detecting molecules")):
            try:
                # Get page image
                page_image = page.page_image
                if page_image is None:
                    print(f"Warning: No image available for page {page_idx}")
                    results.append({'molecules': [], 'tables': []})
                    continue
                
                # Convert to PIL Image if needed
                if not isinstance(page_image, Image.Image):
                    if hasattr(page_image, 'image'):
                        page_image = page_image.image
                    else:
                        page_image = Image.fromarray(page_image)
                
                # Molecule detection
                molecules = []
                if self.processor_config.get('with_mol_detect', True):
                    # mol_results 格式
                    # [
                    #   {
                    #      'bbox': [x1, y1, x2, y2], 
                    #      'confidence': 0.9, 
                    #      'data': {'smiles': 'c1ccccc1', 'mock': False}
                    #    }
                    # ]
                    mol_results = self.processor.moldect_with_test_augment(
                        image=page_image,
                        moldetect_model=self.processor.mol_detection_model,
                        offset_x=0,
                        offset_y=0,
                        usr_tta=self.processor_config.get('use_tta', True),
                        coref=self.processor_config.get('coref', True),
                        use_ocr=False,
                        with_padding=False,
                        dubug=self.processor_config.get('debug', False)
                    )
                    
                    # Process molecule results
                    for mol_result in mol_results:
                        if 'bbox' in mol_result:
                            bbox = mol_result['bbox']
                            # Convert to our bbox format
                            bbox = [bbox[0], bbox[1], bbox[2], bbox[3]]
                            molecules.append({
                                'bbox': bbox,
                                'confidence': mol_result.get('confidence', 1.0),
                                'data': mol_result
                            })
                
                # Table detection  
                tables = []
                if self.processor_config.get('with_table_detect', True):
                    # table_results 格式
                    # {
                    #   'tables_layout': [
                    #     {'bbox': [x1, y1, x2, y2], 'confidence': 0.9, 'data': {'html_content': '<table>...</table>', 'mock': True}}
                    #   ]
                    # }
                    table_results = self.processor.single_page_table_detection(page_image)
                    
                    # Extract tables_layout from the results
                    tables_layout = table_results.get('tables_layout', [])
                    
                    # Process table results
                    for table_layout in tables_layout:
                        # table_layout should have bbox information
                        if 'bbox' in table_layout:
                            bbox = table_layout['bbox']
                            tables.append({
                                'bbox': bbox,
                                'confidence': table_layout.get('confidence', 1.0),
                                'data': table_layout
                            })
                
                results.append({
                    'page_idx': page_idx,
                    'molecules': molecules,
                    'tables': tables
                })
                
            except Exception as e:
                print(f"Error detecting molecules/tables on page {page_idx}: {e}")
                results.append({'page_idx': page_idx, 'molecules': [], 'tables': []})
        
        return results

    def _bbox_to_polygon(self, bbox):
        """
        将bbox转换为polygon格式
        bbox格式: [x1, y1, x2, y2]
        polygon格式: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
        """

        return PolygonBox.from_bbox(bbox)

    def merge_molecule_blocks_to_pages(self, pages: List[PageGroup], detection_results: List[dict]):
        """
        Merge detected molecules and tables into page structures
        
        Args:
            pages: List of page groups to modify
            detection_results: Detection results from img2mol or mock data
        """
        print('merge_molecule_blocks_to_pages', detection_results)
        for page_result in detection_results:
            page_idx = page_result.get('page_idx', 0)
            if page_idx >= len(pages):
                print('page_idx', page_idx)
                continue
                
            page = pages[page_idx]
            new_blocks = []
            
            # Process molecule detections
            for molecule_detection in page_result.get('molecules', []):
                bbox = molecule_detection.get('bbox', [])
                if len(bbox) != 4:
                    continue
                    
                polygon = self._bbox_to_polygon(bbox)
                
                if self.use_mock_data:
                    # Mock数据
                    structure_data = {
                        'smiles': 'c1ccccc1',
                        'formula': 'C6H6',
                        'mock': True
                    }
                else:
                    # 真实数据
                    structure_data = molecule_detection.get('data', {})
                
                # Create molecule block with proper page_id
                mol_block = Molecule(
                    polygon=polygon,
                    page_id=page.page_id,
                    structure_data=structure_data,
                    confidence=molecule_detection.get('confidence', 1.0)
                )
                print('append!!')
                new_blocks.append(mol_block)
            
            # Process table detections  
            for table_detection in page_result.get('tables', []):
                bbox = table_detection.get('bbox', [])
                if len(bbox) != 4:
                    continue
                    
                polygon = self._bbox_to_polygon(bbox)
                table_data = table_detection.get('data', {})
                
                # 获取HTML内容
                html_content = table_data.get('html_content', '')
                
                # 调试信息
                source = table_data.get('source', 'unknown')
                original_bbox = table_data.get('original_bbox')
                if original_bbox:
                    print(f"🔄 基于已有表格生成分子表格: 原始坐标 {original_bbox} -> 调整后坐标 {bbox}")
                
                # Create molecule table block with proper page_id
                mol_table_block = MoleculeTable(
                    polygon=polygon,
                    page_id=page.page_id,
                    html=html_content,  # 直接使用html字段
                    confidence=table_detection.get('confidence', 1.0)
                )
                new_blocks.append(mol_table_block)
            
            if new_blocks:
                print('new_blocks', new_blocks)
                # Replace overlapping blocks for molecules (any block type with high overlap)
                molecule_blocks = [b for b in new_blocks if isinstance(b, Molecule)]
                if molecule_blocks:
                    print('molecule_blocks', molecule_blocks)
                    self._replace_overlapping_blocks(
                        page, 
                        molecule_blocks, 
                        self.overlap_threshold
                    )
                
                # Replace overlapping blocks for tables (specifically target Table blocks) 
                table_blocks = [b for b in new_blocks if isinstance(b, MoleculeTable)]
                if table_blocks:
                    self._replace_overlapping_blocks(
                        page,
                        table_blocks, 
                        self.table_overlap_threshold,
                        target_types=[BlockTypes.Table]
                    )

    def _replace_overlapping_blocks(self, page: PageGroup, new_blocks: List, 
                                   threshold: float, exclude_types: List = None, 
                                   target_types: List = None):
        """
        Replace overlapping blocks with new molecule/table blocks
        
        Args:
            page: The page containing blocks to check
            new_blocks: List of new blocks to add  
            threshold: Overlap threshold (0-1)
            exclude_types: Block types to exclude from replacement
            target_types: Only replace blocks of these types (if specified)
        """
        if not new_blocks:
            return
            
        if exclude_types is None:
            exclude_types = []
            
        blocks_to_replace = []  # (old_block, new_block) pairs
        blocks_to_add = []      # new blocks with no overlap
        
        for new_block in new_blocks:
            replaced_existing = False
            
            # Check overlap with existing blocks
            for existing_block in page.current_children:  # Use current_children to get non-removed blocks
                # Skip if block type is excluded
                if existing_block.block_type in exclude_types:
                    continue
                    
                # If target_types specified, only replace those types
                if target_types and existing_block.block_type not in target_types:
                    continue
                
                # Calculate overlap percentage
                overlap_pct = existing_block.polygon.intersection_pct(new_block.polygon)
                
                if overlap_pct >= threshold:
                    # Replace this block
                    blocks_to_replace.append((existing_block, new_block))
                    replaced_existing = True
                    break  # Each new block replaces at most one existing block
                    
            if not replaced_existing:
                # No overlap found, add as new block
                blocks_to_add.append(new_block)
        
        # Execute the replacements and additions
        self._execute_block_operations(page, blocks_to_replace, blocks_to_add)

    def _execute_block_operations(self, page: PageGroup, blocks_to_replace: List, blocks_to_add: List):
        """
        Execute block replacement and addition operations using proper page methods
        
        Args:
            page: The page to modify
            blocks_to_replace: List of (old_block, new_block) tuples
            blocks_to_add: List of new blocks to add
        """
        # Replace existing blocks
        for old_block, new_block in blocks_to_replace:
            # Set proper page_id for the new block
            new_block.page_id = page.page_id
            page.replace_block(old_block, new_block)
        
        # Add new blocks
        for block_to_add in blocks_to_add:
            # Set proper page_id for the new block
            block_to_add.page_id = page.page_id
            page.add_full_block(block_to_add)
            # Also add to page structure for proper ordering
            page.structure.append(block_to_add.id) 
