#!/usr/bin/env python3
"""
增强版分子识别extraction测试脚本

测试marker_main.ExtractionProc的extraction方法，包含分子识别功能
包含对marker_main的扩展以正确支持分子检测
"""

import os
import sys
import time
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/home/luohao/codes/gpt-marker')

from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.settings import settings
from marker.logger import configure_logging
from marker.models import create_model_dict
from marker.utils import send_callback, flush_cuda_memory
from datetime import datetime
import pytz

# 获取北京时区
beijing_tz = pytz.timezone('Asia/Shanghai')

configure_logging()


class MoleculeExtractionProc:
    """
    增强版ExtractionProc，支持分子识别
    """
    def __init__(self, config=None):
        self.model_lst = []
        self.model_dict = None
    
    def load_models(self):
        """加载所有必需的模型"""
        self.model_dict = create_model_dict()
    
    def extraction_with_molecules(self, args, file_byte, callback_url='', docId='', file_type='pdf'):
        """
        增强版extraction方法，支持分子识别
        
        Args:
            args: 配置参数
            file_byte: 文件字节数据
            callback_url: 回调URL
            docId: 文档ID
            file_type: 文件类型
        
        Returns:
            tuple: (full_text, None, info, metadata)
        """
        start = time.time()
        
        # 准备kwargs
        kwargs = {
            'output_dir': args.get('output_dir', settings.OUTPUT_DIR),
            'debug': args.get('debug', False),
            'output_format': args.get('output_format', 'markdown'),
            'page_range': args.get('page_range', None),
            'force_ocr': args.get('force_ocr', False),
            'processors': args.get('processors', None),
            'config_json': args.get('config_json', None),
            'languages': args.get('languages', None),
            'disable_multiprocessing': args.get('disable_multiprocessing', False),
            'paginate_output': args.get('paginate_output', False),
            'disable_image_extraction': args.get('disable_image_extraction', False),
        }
        
        # 解析配置
        config_parser = ConfigParser(kwargs)
        config_dict = config_parser.generate_config_dict()
        
        # 处理分子检测配置
        config_json_str = args.get('config_json')
        config_json = {}
        if config_json_str:
            try:
                if isinstance(config_json_str, str):
                    config_json = json.loads(config_json_str)
                elif isinstance(config_json_str, dict):
                    config_json = config_json_str  # 兼容旧格式
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse config_json: {e}")
                config_json = {}
        
        if config_json:
            # 将config_json中的配置合并到config_dict
            config_dict.update(config_json)
            
            # 如果有processor_config，添加到artifact_dict
            processor_config = config_json.get('processor_config')
            if processor_config:
                self.model_dict["processor_config"] = processor_config
        
        # 发送开始回调
        time_str = datetime.now(beijing_tz).strftime("%H:%M:%S")
        send_callback(callback_url, {
            'status': True,
            'messages': 'success',
            'docId': docId,
            'progress': 5,
            'progress_text': '开始解析  ' + time_str
        })
        
        print(f"🔧 配置信息:")
        print(f"  - 分子检测: {config_dict.get('use_molecule_detection', False)}")
        print(f"  - LLM: {config_dict.get('use_llm', False)}")
        print(f"  - 调试模式: {config_dict.get('debug', False)}")
        
        # 创建PdfConverter
        converter = PdfConverter(
            config=config_dict,
            artifact_dict=self.model_dict,
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            callback_url=callback_url,
            docId=docId,
            llm_service="marker.services.gemini.GoogleGeminiService"
        )
        
        # 执行转换
        print(f"🚀 开始PDF转换...")
        rendered = converter(file_byte, file_type=file_type)
        
        # 统计结果
        info = self.count_table_formula(rendered.metadata)
        full_text = rendered.markdown
        
        processing_time = time.time() - start
        print(f'✅ 转换完成，用时: {processing_time:.2f}秒')

        return full_text, None, info, rendered.metadata
    
    def count_table_formula(self, metadata):
        """统计表格和公式数量"""
        table_count = 0
        formula_count = 0
        ocr_count = 0
        molecule_count = 0
        molecule_table_count = 0
        
        for page in metadata['page_stats']:
            meta = page['block_counts']
            extract_method = page['text_extraction_method']
            for i in meta:
                if i[0] == 'Table':
                    table_count += i[1]
                elif i[0] == 'Equation':
                    formula_count += i[1]
                elif i[0] == 'Molecule':
                    molecule_count += i[1]
                elif i[0] == 'MoleculeTable':
                    molecule_table_count += i[1]
            if extract_method != 'pdftext':
                ocr_count += 1
        
        return {
            'table_count': table_count,
            'formula_count': formula_count,
            'ocr_count': ocr_count,
            'molecule_count': molecule_count,
            'molecule_table_count': molecule_table_count
        }


def create_molecule_test_args(
    output_dir: str = "./test_output",
    debug: bool = True,
    force_ocr: bool = False,
    processor_config: dict = None,
    use_mock_data: bool = True  # 默认使用mock数据进行快速测试
):
    """
    创建分子识别测试参数
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
        "use_mock_data": use_mock_data,  # 添加mock模式配置
        "mock_mode": use_mock_data  # 别名
    }
    
    if processor_config:
        default_processor_config.update(processor_config)
    
    # 创建config_json - 作为JSON字符串
    config_dict = {
        "use_molecule_detection": True,
        "use_llm": False,  # 可以根据需要启用
        "processor_config": default_processor_config
    }
    config_json = json.dumps(config_dict)
    
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


def test_molecule_extraction_enhanced(
    pdf_path: str,
    output_dir: str = "./test_output",
    callback_url: str = "",
    doc_id: str = "test_doc",
    processor_config: dict = None,
    custom_args: dict = None,
    use_mock_data: bool = True  # 默认使用mock数据
):
    """
    增强版分子识别extraction测试
    """
    
    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🧪 增强版分子识别Extraction测试")
    print(f"📄 PDF文件: {pdf_path}")
    print(f"📁 输出目录: {output_dir}")
    print(f"🆔 文档ID: {doc_id}")
    print(f"🎭 Mock模式: {'启用' if use_mock_data else '禁用'}")
    print("-" * 80)
    
    # 初始化增强版ExtractionProc
    print("⚙️  初始化MoleculeExtractionProc...")
    proc = MoleculeExtractionProc()
    
    # 加载模型
    print("🤖 加载模型...")
    proc.load_models()
    
    # 读取PDF文件
    print("📖 读取PDF文件...")
    with open(pdf_path, 'rb') as f:
        file_byte = f.read()
    
    # 创建测试参数
    print("🔧 配置分子识别参数...")
    if custom_args:
        args = custom_args
    else:
        args = create_molecule_test_args(
            output_dir=output_dir,
            debug=True,
            processor_config=processor_config,
            use_mock_data=use_mock_data
        )
    
    # 显示配置信息
    print("🔍 当前配置:")
    config_json_str = args.get('config_json', '{}')
    config_json = {}
    if config_json_str:
        try:
            if isinstance(config_json_str, str):
                config_json = json.loads(config_json_str)
            elif isinstance(config_json_str, dict):
                config_json = config_json_str  # 兼容旧格式
        except json.JSONDecodeError:
            config_json = {}
    
    print(f"  - 启用分子检测: {config_json.get('use_molecule_detection', False)}")
    print(f"  - 启用LLM: {config_json.get('use_llm', False)}")
    print(f"  - 调试模式: {args.get('debug', False)}")
    print(f"  - 强制OCR: {args.get('force_ocr', False)}")
    
    if 'processor_config' in config_json:
        pc = config_json['processor_config']
        print(f"  - 设备: {pc.get('device', 'unknown')}")
        print(f"  - 分子检测: {pc.get('with_mol_detect', False)}")
        print(f"  - 表格检测: {pc.get('with_table_detect', False)}")
        print(f"  - YOLO分子模型: {pc.get('use_yolo_mol_model', False)}")
        print(f"  - YOLO表格模型: {pc.get('use_yolo_table_model', False)}")
        print(f"  - Mock模式: {pc.get('use_mock_data', False)}")
    
    print("-" * 80)
    
    # 开始extraction
    print("🚀 开始extraction...")
    start_time = time.time()
    
    try:
        full_text, _, info, metadata = proc.extraction_with_molecules(
            args=args,
            file_byte=file_byte,
            callback_url=callback_url,
            docId=doc_id,
            file_type='pdf'
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print("✅ Extraction完成!")
        print(f"⏱️  总处理时间: {processing_time:.2f}秒")
        
        # 分析结果
        print("\n📊 提取结果分析:")
        print(f"  - 文本长度: {len(full_text):,} 字符")
        print(f"  - 普通表格数量: {info.get('table_count', 0)}")
        print(f"  - 公式数量: {info.get('formula_count', 0)}")
        print(f"  - OCR页面数: {info.get('ocr_count', 0)}")
        print(f"  - 分子结构数量: {info.get('molecule_count', 0)}")
        print(f"  - 分子表格数量: {info.get('molecule_table_count', 0)}")
        
        # 文本中的分子标签统计
        text_mol_count = full_text.count('<mol>')
        text_mol_table_count = full_text.count('<mol_table>')
        print(f"  - 文本中<mol>标签: {text_mol_count}")
        print(f"  - 文本中<mol_table>标签: {text_mol_table_count}")
        
        # 保存结果
        output_file = os.path.join(output_dir, f"{doc_id}_enhanced_molecules.md")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"💾 结果已保存到: {output_file}")
        
        # 保存metadata
        metadata_file = os.path.join(output_dir, f"{doc_id}_enhanced_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"📋 元数据已保存到: {metadata_file}")
        
        # 保存配置信息
        config_file = os.path.join(output_dir, f"{doc_id}_config.json")
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(args, f, indent=2, ensure_ascii=False)
        print(f"⚙️  配置已保存到: {config_file}")
        
        # 显示示例输出
        if text_mol_count > 0 or text_mol_table_count > 0:
            print("\n🧬 分子识别示例输出:")
            lines = full_text.split('\n')
            shown_examples = 0
            for i, line in enumerate(lines):
                if ('<mol>' in line or '<mol_table>' in line) and shown_examples < 3:
                    start_idx = max(0, i-2)
                    end_idx = min(len(lines), i+3)
                    print(f"  示例 {shown_examples + 1}:")
                    print("  " + "-" * 50)
                    for j in range(start_idx, end_idx):
                        marker = "👉 " if j == i else "   "
                        line_content = lines[j][:100] + "..." if len(lines[j]) > 100 else lines[j]
                        print(f"  {marker}{line_content}")
                    print("  " + "-" * 50)
                    shown_examples += 1
        else:
            print("\n⚠️  未检测到分子标签，可能的原因:")
            print("   - PDF中没有化学分子结构")
            print("   - img2mol模型未正确加载")
            print("   - 分子检测配置有误")
            print("   - 图像质量不够好")
        
        return {
            'success': True,
            'full_text': full_text,
            'info': info,
            'metadata': metadata,
            'processing_time': processing_time,
            'text_mol_count': text_mol_count,
            'text_mol_table_count': text_mol_table_count,
            'output_file': output_file,
            'config_file': config_file
        }
        
    except Exception as e:
        print(f"❌ Extraction失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """主函数"""
    
    print("🧪 增强版分子识别Extraction测试脚本")
    print("=" * 80)
    
    # 检查命令行参数
    use_real_model = '--real' in sys.argv  # 使用 --real 参数启用真实模型
    use_mock_data = not use_real_model  # 默认使用mock模式
    
    # 单个测试示例
    single_test_config = {
        'pdf_path': 'data/molecule.pdf',  # 使用用户设置的路径
        'output_dir': './molecule_enhanced_test',
        'doc_id': 'enhanced_test',
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
        },
        'use_mock_data': use_mock_data
    }
    
    # 检查是否要运行综合测试
    if len(sys.argv) > 1 and sys.argv[1] == '--comprehensive':
        run_comprehensive_test(use_mock_data=use_mock_data)
        return
    
    # 显示运行模式
    if use_mock_data:
        print("🎭 运行模式: Mock测试模式 (快速测试)")
        print("   - 将生成假的分子检测数据")
        print("   - 输出固定内容: <mol>c1ccccc1</mol> 和 <mol_table>placeholder</mol_table>")
        print("   - 不需要img2mol依赖")
        print("   - 使用 --real 参数启用真实模型测试")
    else:
        print("🔬 运行模式: 真实模型测试")
        print("   - 将使用img2mol进行真实的分子检测")
        print("   - 需要安装img2mol依赖和模型文件")
    
    print("-" * 80)
    
    # 检查PDF文件
    pdf_path = single_test_config['pdf_path']
    if not os.path.exists(pdf_path):
        print(f"❌ 测试PDF文件不存在: {pdf_path}")
        print("\n📝 使用说明:")
        print("1. 请修改single_test_config['pdf_path']为实际PDF文件路径")
        print("2. 运行Mock测试: python test_molecule_extraction_enhanced.py")
        print("3. 运行真实模型测试: python test_molecule_extraction_enhanced.py --real")
        print("4. 运行综合测试: python test_molecule_extraction_enhanced.py --comprehensive")
        return
    
    # 运行单个测试
    try:
        result = test_molecule_extraction_enhanced(**single_test_config)
        
        if result['success']:
            print(f"\n🎉 测试成功完成!")
            print(f"📄 输出文件: {result['output_file']}")
            print(f"🧬 识别分子结构: {result['text_mol_count']}")
            print(f"📊 识别分子表格: {result['text_mol_table_count']}")
            print(f"⏱️  处理时间: {result['processing_time']:.2f}秒")
            
            if result['text_mol_count'] > 0 or result['text_mol_table_count'] > 0:
                print("\n✨ 分子识别功能工作正常！")
                if use_mock_data:
                    print("🎭 Mock模式测试通过，可以尝试使用 --real 参数测试真实模型")
            else:
                print("\n⚠️  未检测到分子内容，请检查PDF和配置")
        else:
            print(f"\n❌ 测试失败: {result['error']}")
            
    except Exception as e:
        print(f"\n💥 测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()


def run_comprehensive_test(use_mock_data: bool = True):
    """运行综合测试"""
    
    # 测试配置
    test_configs = [
        {
            'name': '基础分子检测测试',
            'pdf_path': 'data/molecule.pdf',  # 使用用户设置的路径
            'processor_config': {
                'device': 'cuda',
                'with_mol_detect': True,
                'with_table_detect': True,
                'debug': True,
            },
            'use_mock_data': use_mock_data
        },
        {
            'name': '高精度分子检测测试',
            'pdf_path': 'data/molecule.pdf',  # 使用用户设置的路径
            'processor_config': {
                'device': 'cuda',
                'with_mol_detect': True,
                'with_table_detect': True,
                'use_yolo_mol_model': True,
                'use_yolo_table_model': True,
                'use_yolo_table_model_v2': True,
                'debug': True,
                'num_workers': 1,
            },
            'use_mock_data': use_mock_data
        }
    ]
    
    mode_name = "Mock测试" if use_mock_data else "真实模型测试"
    print(f"🧪 综合分子识别测试 - {mode_name}")
    print("=" * 80)
    
    results = []
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n🔬 测试 {i}: {config['name']} ({mode_name})")
        print("-" * 60)
        
        if not os.path.exists(config['pdf_path']):
            print(f"❌ 跳过测试 {i}: PDF文件不存在 {config['pdf_path']}")
            results.append({'test_name': config['name'], 'success': False, 'error': 'PDF file not found'})
            continue
        
        try:
            result = test_molecule_extraction_enhanced(
                pdf_path=config['pdf_path'],
                output_dir=f'./test_output_{i}',
                doc_id=f'test_{i}',
                processor_config=config['processor_config'],
                use_mock_data=config['use_mock_data']
            )
            
            result['test_name'] = config['name']
            results.append(result)
            
            if result['success']:
                print(f"✅ 测试 {i} 成功!")
                print(f"   - 分子结构: {result['text_mol_count']}")
                print(f"   - 分子表格: {result['text_mol_table_count']}")
                print(f"   - 处理时间: {result['processing_time']:.2f}秒")
            else:
                print(f"❌ 测试 {i} 失败: {result['error']}")
                
        except Exception as e:
            print(f"💥 测试 {i} 异常: {str(e)}")
            results.append({'test_name': config['name'], 'success': False, 'error': str(e)})
    
    # 总结报告
    print("\n" + "=" * 80)
    print(f"📋 {mode_name}总结报告")
    print("=" * 80)
    
    successful_tests = [r for r in results if r.get('success', False)]
    failed_tests = [r for r in results if not r.get('success', False)]
    
    print(f"✅ 成功测试: {len(successful_tests)}/{len(results)}")
    print(f"❌ 失败测试: {len(failed_tests)}/{len(results)}")
    
    if successful_tests:
        total_molecules = sum(r.get('text_mol_count', 0) for r in successful_tests)
        total_mol_tables = sum(r.get('text_mol_table_count', 0) for r in successful_tests)
        avg_time = sum(r.get('processing_time', 0) for r in successful_tests) / len(successful_tests)
        
        print(f"🧬 总检测分子: {total_molecules}")
        print(f"📊 总检测分子表格: {total_mol_tables}")
        print(f"⏱️  平均处理时间: {avg_time:.2f}秒")
    
    if failed_tests:
        print(f"\n❌ 失败的测试:")
        for test in failed_tests:
            print(f"   - {test['test_name']}: {test.get('error', 'Unknown error')}")
    
    return results


if __name__ == "__main__":
    main() 