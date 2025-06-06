#!/usr/bin/env python3
"""
分子识别extraction测试脚本

测试marker_main.ExtractionProc的extraction方法，包含分子识别功能
"""

import os
import sys
import time
import json
from pathlib import Path
import argparse

# 添加项目路径
sys.path.insert(0, '/home/luohao/codes/gpt-marker')

from marker_main import ExtractionProc
from marker.models import create_model_dict


def create_test_args_with_molecule_detection(
    output_dir: str = "./test_output",
    debug: bool = True,
    force_ocr: bool = False,
    use_molecule_detection: bool = True,
    processor_config: dict = None,
    use_mock_data: bool = True  # 默认使用mock数据
):
    """
    创建包含分子识别的测试参数
    
    Args:
        output_dir: 输出目录
        debug: 是否启用调试模式
        force_ocr: 是否强制OCR
        use_molecule_detection: 是否启用分子检测
        processor_config: img2mol processor配置
        use_mock_data: 是否使用mock数据
    
    Returns:
        配置好的参数字典
    """
    
    # 默认分子识别配置
    default_processor_config = {
        "device": "cuda",
        "with_mol_detect": True,
        "with_table_detect": True,
        "use_yolo_mol_model": True,
        "use_yolo_table_model": True,
        "use_yolo_table_model_v2": True,
        "debug": debug,
        "num_workers": 1,
        "padding": 0,
        "use_mock_data": use_mock_data,
        "mock_mode": use_mock_data
    }
    
    if processor_config:
        default_processor_config.update(processor_config)
    
    # 创建config_json，包含分子检测配置
    config_json = {
        "use_molecule_detection": use_molecule_detection,
        "use_llm": False,  # 可以根据需要启用
        "processor_config": default_processor_config if use_molecule_detection else {}
    }
    args = {
        'output_dir': output_dir,
        'debug': debug,
        'output_format': 'markdown',
        'page_range': None,
        'force_ocr': force_ocr,
        'processors': None,
        'config_json': config_json,  # 现在是JSON字符串
        'languages': None,
        'disable_multiprocessing': False,
        'paginate_output': False,
        'disable_image_extraction': False,
    }
    
    return args


def test_molecule_extraction(
    pdf_path: str,
    output_dir: str = "./test_output",
    callback_url: str = "",
    doc_id: str = "test_doc",
    processor_config: dict = None
):
    """
    测试分子识别extraction功能
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        callback_url: 回调URL（可选）
        doc_id: 文档ID
        processor_config: processor配置
    
    Returns:
        提取结果
    """
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🧪 开始测试分子识别extraction功能")
    print(f"📄 PDF文件: {pdf_path}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🆔 文档ID: {doc_id}")
    print("-" * 60)
    
    # 初始化ExtractionProc
    print("⚙️  初始化ExtractionProc...")
    proc = ExtractionProc()
    
    # 加载模型
    print("🤖 加载模型...")
    proc.load_models()
    
    # 如果启用分子检测，需要在model_dict中添加processor_config
    if processor_config:
        if not hasattr(proc, 'model_dict'):
            proc.model_dict = create_model_dict()
        proc.model_dict["processor_config"] = processor_config
    
    # 读取PDF文件
    print("📖 读取PDF文件...")
    with open(pdf_path, 'rb') as f:
        file_byte = f.read()
    
    # 创建测试参数
    print("🔧 配置分子识别参数...")
    args = create_test_args_with_molecule_detection(
        output_dir=output_dir,
        debug=True,
        processor_config=processor_config
    )
    
    print("🔍 分子识别配置:")
    config_json = args['config_json']
    print(f"  - 启用分子检测: {config_json.get('use_molecule_detection', False)}")
    print(f"  - 启用LLM: {config_json.get('use_llm', False)}")
    if 'processor_config' in config_json:
        pc = config_json['processor_config']
        print(f"  - 设备: {pc.get('device', 'unknown')}")
        print(f"  - 分子检测: {pc.get('with_mol_detect', False)}")
        print(f"  - 表格检测: {pc.get('with_table_detect', False)}")
    
    print("-" * 60)
    
    # 开始extraction
    print("🚀 开始extraction...")
    start_time = time.time()
    
    try:
        full_text, _, info, metadata = proc.extraction(
            args=args,
            file_byte=file_byte,
            callback_url=callback_url,
            docId=doc_id,
            file_type='pdf'
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print("✅ Extraction完成!")
        print(f"⏱️  处理时间: {processing_time:.2f}秒")
        
        # 分析结果
        print("\n📊 提取结果分析:")
        print(f"  - 文本长度: {len(full_text)} 字符")
        print(f"  - 表格数量: {info.get('table_count', 0)}")
        print(f"  - 公式数量: {info.get('formula_count', 0)}")
        print(f"  - OCR页面数: {info.get('ocr_count', 0)}")
        
        # 分子识别结果分析
        mol_count = full_text.count('<mol>')
        mol_table_count = full_text.count('<mol_table>')
        print(f"  - 分子结构数量: {mol_count}")
        print(f"  - 分子表格数量: {mol_table_count}")
        
        # 保存结果
        output_file = os.path.join(output_dir, f"{doc_id}_with_molecules.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"💾 结果已保存到: {output_file}")
        
        # 保存metadata
        metadata_file = os.path.join(output_dir, f"{doc_id}_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"📋 元数据已保存到: {metadata_file}")
        
        # 显示示例输出
        if mol_count > 0 or mol_table_count > 0:
            print("\n🧬 分子识别示例输出:")
            lines = full_text.split('\n')
            for i, line in enumerate(lines):
                if '<mol>' in line or '<mol_table>' in line:
                    start_idx = max(0, i-2)
                    end_idx = min(len(lines), i+3)
                    print("  " + "-" * 40)
                    for j in range(start_idx, end_idx):
                        marker = "👉 " if j == i else "   "
                        print(f"  {marker}{lines[j]}")
                    print("  " + "-" * 40)
                    break
        
        return {
            'success': True,
            'full_text': full_text,
            'info': info,
            'metadata': metadata,
            'processing_time': processing_time,
            'mol_count': mol_count,
            'mol_table_count': mol_table_count,
            'output_file': output_file
        }
        
    except Exception as e:
        print(f"❌ Extraction失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def test_molecule_table_mock_generation():
    """
    测试分子表格mock数据生成和覆盖功能
    """
    print("🧪 测试分子表格Mock数据生成和覆盖功能")
    print("=" * 60)
    
    try:
        from marker.builders.molecule_layout import MoleculeLayoutBuilder
        
        # 测试HTML表格生成
        builder = MoleculeLayoutBuilder()
        print("1. 测试HTML表格生成:")
        for i in range(3):
            html_table = builder._generate_mock_molecule_table_html()
            print(f"\n样本 {i+1}:")
            print(html_table[:200] + "..." if len(html_table) > 200 else html_table)
            
            # 验证包含C1CCCCC1等分子
            if 'C1CCCCC1' in html_table or 'c1ccccc1' in html_table:
                print("✅ 包含目标分子SMILES")
            else:
                print("❌ 未包含目标分子SMILES")
        
        print("\n" + "=" * 60)
        print("✅ 分子表格Mock数据生成测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数 - 运行测试"""
    
    print("🧪 分子识别Extraction测试脚本")
    print("=" * 60)
    
    # 检查命令行参数
    use_real_model = '--real' in sys.argv  # 使用 --real 参数启用真实模型
    use_mock_data = not use_real_model  # 默认使用mock模式
    
    # 测试配置
    test_config = {
        'pdf_path': 'data/molecule.pdf',  # 请修改为实际路径
        'output_dir': './molecule_test_output',
        'doc_id': 'chemistry_test',
        'processor_config': {
            'device': 'cuda',  # 或 'cpu'
            'with_mol_detect': True,
            'with_table_detect': True,
            'use_yolo_mol_model': True,
            'use_yolo_table_model': True,
            'use_yolo_table_model_v2': True,
            'debug': True,
            'num_workers': 1,
            'padding': 0,
            # 添加更多img2mol配置...
        }
    }
    
    # 显示运行模式
    if use_mock_data:
        print("🎭 运行模式: Mock测试模式 (快速测试)")
        print("   - 使用 --real 参数启用真实模型测试")
    else:
        print("🔬 运行模式: 真实模型测试")
    
    print("-" * 60)
    
    # 检查PDF文件
    pdf_path = test_config['pdf_path']
    if not os.path.exists(pdf_path):
        print(f"❌ 测试PDF文件不存在: {pdf_path}")
        print("\n📝 使用说明:")
        print("1. 请将test_config['pdf_path']设置为实际的PDF文件路径")
        print("2. Mock测试: python test_molecule_extraction.py")
        print("3. 真实模型测试: python test_molecule_extraction.py --real")
        return
    
    # 运行测试
    try:
        # 修改test_molecule_extraction函数调用，添加use_mock_data参数
        result = test_molecule_extraction_with_mock(**test_config, use_mock_data=use_mock_data)
        
        if result['success']:
            print(f"\n🎉 测试成功完成!")
            print(f"📄 输出文件: {result['output_file']}")
            print(f"🧬 识别到 {result['mol_count']} 个分子结构")
            print(f"📊 识别到 {result['mol_table_count']} 个分子表格")
            print(f"⏱️  总处理时间: {result['processing_time']:.2f}秒")
            
            if result['mol_count'] > 0 or result['mol_table_count'] > 0:
                print("\n✨ 分子识别功能工作正常！")
                if use_mock_data:
                    print("🎭 Mock模式测试通过，可以尝试使用 --real 参数测试真实模型")
            else:
                print("\n⚠️  未检测到分子内容，可能的原因:")
                print("   - PDF中没有化学分子结构")
                print("   - 分子检测模型未正确加载")
                print("   - 图像质量不足")
        else:
            print(f"\n❌ 测试失败: {result['error']}")
            
    except Exception as e:
        print(f"\n💥 测试脚本执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


def test_molecule_extraction_with_mock(
    pdf_path: str,
    output_dir: str = "./test_output",
    callback_url: str = "",
    doc_id: str = "test_doc",
    processor_config: dict = None,
    use_mock_data: bool = True
):
    """
    带mock支持的分子识别extraction测试
    """
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🧪 开始测试分子识别extraction功能")
    print(f"📄 PDF文件: {pdf_path}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🆔 文档ID: {doc_id}")
    print(f"🎭 Mock模式: {'启用' if use_mock_data else '禁用'}")
    print("-" * 60)
    
    # 初始化ExtractionProc
    print("⚙️  初始化ExtractionProc...")
    proc = ExtractionProc()
    
    # 加载模型
    print("🤖 加载模型...")
    proc.load_models()
    
    # 如果启用分子检测，需要在model_dict中添加processor_config
    if processor_config:
        if not hasattr(proc, 'model_dict'):
            proc.model_dict = create_model_dict()
        proc.model_dict["processor_config"] = processor_config
    
    # 读取PDF文件
    print("📖 读取PDF文件...")
    with open(pdf_path, 'rb') as f:
        file_byte = f.read()
    
    # 创建测试参数
    print("🔧 配置分子识别参数...")
    args = create_test_args_with_molecule_detection(
        output_dir=output_dir,
        debug=True,
        processor_config=processor_config,
        use_mock_data=use_mock_data
    )
    
    print("🔍 分子识别配置:")
    config_json = args['config_json']
    
    print(f"  - 启用分子检测: {config_json.get('use_molecule_detection', False)}")
    print(f"  - 启用LLM: {config_json.get('use_llm', False)}")
    if 'processor_config' in config_json:
        pc = config_json['processor_config']
        print(f"  - 设备: {pc.get('device', 'unknown')}")
        print(f"  - 分子检测: {pc.get('with_mol_detect', False)}")
        print(f"  - 表格检测: {pc.get('with_table_detect', False)}")
        print(f"  - Mock模式: {pc.get('use_mock_data', False)}")
    
    print("-" * 60)
    
    # 开始extraction
    print("🚀 开始extraction...")
    start_time = time.time()
    
    try:
        full_text, _, info, metadata = proc.extraction(
            args=args,
            file_byte=file_byte,
            callback_url=callback_url,
            docId=doc_id,
            file_type='pdf'
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print("✅ Extraction完成!")
        print(f"⏱️  处理时间: {processing_time:.2f}秒")
        
        # 分析结果
        print("\n📊 提取结果分析:")
        print(f"  - 文本长度: {len(full_text)} 字符")
        print(f"  - 表格数量: {info.get('table_count', 0)}")
        print(f"  - 公式数量: {info.get('formula_count', 0)}")
        print(f"  - OCR页面数: {info.get('ocr_count', 0)}")
        
        # 分子识别结果分析
        mol_count = full_text.count('<mol>')
        mol_table_count = full_text.count('<mol_table>')
        print(f"  - 分子结构数量: {mol_count}")
        print(f"  - 分子表格数量: {mol_table_count}")
        
        # 保存结果
        output_file = os.path.join(output_dir, f"{doc_id}_with_molecules.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"💾 结果已保存到: {output_file}")
        
        # 保存metadata
        metadata_file = os.path.join(output_dir, f"{doc_id}_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"📋 元数据已保存到: {metadata_file}")
        
        # 显示示例输出
        if mol_count > 0 or mol_table_count > 0:
            print("\n🧬 分子识别示例输出:")
            lines = full_text.split('\n')
            for i, line in enumerate(lines):
                if '<mol>' in line or '<mol_table>' in line:
                    start_idx = max(0, i-2)
                    end_idx = min(len(lines), i+3)
                    print("  " + "-" * 40)
                    for j in range(start_idx, end_idx):
                        marker = "👉 " if j == i else "   "
                        print(f"  {marker}{lines[j]}")
                    print("  " + "-" * 40)
                    break
        
        return {
            'success': True,
            'full_text': full_text,
            'info': info,
            'metadata': metadata,
            'processing_time': processing_time,
            'mol_count': mol_count,
            'mol_table_count': mol_table_count,
            'output_file': output_file
        }
        
    except Exception as e:
        print(f"❌ Extraction失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='测试分子识别功能')
    parser.add_argument('--pdf', type=str, help='PDF文件路径')
    parser.add_argument('--output', type=str, default='./test_output', help='输出目录')
    parser.add_argument('--mock', action='store_true', help='使用mock数据测试')
    parser.add_argument('--real', action='store_true', help='使用真实img2mol模型')
    parser.add_argument('--test-table-mock', action='store_true', help='测试分子表格Mock数据生成')
    
    args = parser.parse_args()
    
    if args.test_table_mock:
        test_molecule_table_mock_generation()
    else:
        # 原有的测试逻辑
        main() 