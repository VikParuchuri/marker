#!/usr/bin/env python3
"""
分子识别集成示例

展示如何使用marker集成img2mol进行化学分子和表格识别
"""

import os
import sys
from typing import Dict, Any

# 添加marker路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from marker.converters.pdf import PdfConverter
from marker.settings import settings


def create_molecule_detection_converter(
    processor_config: Dict[str, Any] = None,
    use_gpu: bool = True,
    model_paths: Dict[str, str] = None
) -> PdfConverter:
    """
    创建支持分子识别的PDF转换器
    
    Args:
        processor_config: img2mol processor的配置参数
        use_gpu: 是否使用GPU
        model_paths: 模型文件路径配置
    
    Returns:
        配置好的PdfConverter实例
    """
    
    # 默认的processor配置
    default_processor_config = {
        "device": "cuda" if use_gpu and settings.TORCH_DEVICE_MODEL == "cuda" else "cpu",
        "with_mol_detect": True,
        "with_table_detect": True,
        "use_yolo_mol_model": True,
        "use_yolo_table_model": True,
        "use_yolo_table_model_v2": True,
        "debug": False,
        "num_workers": 1,
        "padding": 0
    }
    
    # 如果提供了模型路径，添加到配置中
    if model_paths:
        if "mol_model_path" in model_paths:
            default_processor_config["MolDetect_mol_path"] = model_paths["mol_model_path"]
        if "table_model_path" in model_paths:
            default_processor_config["td_model_path"] = model_paths["table_model_path"]
    
    if processor_config:
        default_processor_config.update(processor_config)
    
    # artifact_dict配置
    artifact_dict = {
        "processor_config": default_processor_config,
    }
    
    # converter配置
    config = {
        "use_molecule_detection": True,  # 启用分子检测
        "use_llm": False,  # 根据需要启用LLM
    }
    
    # 创建converter
    converter = PdfConverter(
        artifact_dict=artifact_dict,
        config=config
    )
    
    return converter


def process_pdf_with_molecule_detection(
    pdf_path: str,
    output_path: str = None,
    processor_config: Dict[str, Any] = None,
    model_paths: Dict[str, str] = None
):
    """
    处理包含化学分子的PDF文件
    
    Args:
        pdf_path: PDF文件路径
        output_path: 输出文件路径，如果为None则使用默认路径
        processor_config: processor配置
        model_paths: 模型文件路径配置
    """
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # 创建converter
    converter = create_molecule_detection_converter(
        processor_config=processor_config,
        model_paths=model_paths
    )
    
    try:
        print(f"开始处理PDF: {pdf_path}")
        print("正在进行分子和表格识别...")
        
        # 处理PDF
        result = converter(pdf_path)
        
        # 保存结果
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_path = f"{base_name}_with_molecules.md"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        
        print(f"处理完成！结果已保存到: {output_path}")
        
        # 统计结果
        mol_count = result.count('<mol>')
        mol_table_count = result.count('<mol_table>')
        print(f"检测到 {mol_count} 个分子结构")
        print(f"检测到 {mol_table_count} 个分子表格")
        
        return result
        
    except Exception as e:
        print(f"处理PDF时出错: {e}")
        raise


def main():
    """主函数 - 示例用法"""
    
    # 模型文件路径配置（请根据实际情况修改）
    model_paths = {
        # "mol_model_path": "/path/to/your/mol_detection_model",
        # "table_model_path": "/path/to/your/table_detection_model",
    }
    
    # 示例配置
    processor_config = {
        "device": "cuda",  # 或 "cpu"
        "debug": True,  # 启用调试模式
        "with_mol_detect": True,
        "with_table_detect": True,
        # 可以添加更多配置项
        "use_yolo_mol_model": True,
        "use_yolo_table_model": True,
        "use_yolo_table_model_v2": True,
    }
    
    # 示例PDF路径（请替换为实际路径）
    pdf_path = "example_chemistry_paper.pdf"
    
    if os.path.exists(pdf_path):
        try:
            result = process_pdf_with_molecule_detection(
                pdf_path=pdf_path,
                processor_config=processor_config,
                model_paths=model_paths
            )
            
            print("\n分子识别成功完成！")
            print("输出中包含以下标签：")
            print("- <mol>...</mol>: 化学分子结构")
            print("- <mol_table>...</mol_table>: 包含分子数据的表格")
            print("\n特点：")
            print("- IOU>90%的分子表格会替换原有的普通表格")
            print("- 保持原有的文档结构和顺序")
            print("- 支持各种分子结构和表格格式")
            
        except Exception as e:
            print(f"错误: {e}")
    else:
        print(f"示例PDF文件不存在: {pdf_path}")
        print("请将此脚本中的pdf_path变量设置为实际的PDF文件路径")
        print("\n使用方法:")
        print("1. 确保安装了img2mol及其依赖")
        print("2. 配置模型文件路径（如果需要）")
        print("3. 设置正确的PDF文件路径")
        print("4. 运行脚本")


if __name__ == "__main__":
    main() 