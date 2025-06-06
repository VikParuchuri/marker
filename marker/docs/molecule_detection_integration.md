# 化学分子识别集成指南

本文档介绍如何在marker中集成img2mol进行化学分子和分子表格的识别。

## 概述

通过集成img2mol的`Parser_Processer`，marker现在可以：

1. **检测化学分子结构** - 输出`<mol>...</mol>`标签
2. **检测分子数据表格** - 输出`<mol_table>...</mol_table>`标签  
3. **智能替换原有内容** - 使用IOU>90%的阈值替换重叠的layout blocks

## 系统架构

```
PDF文档 → 标准Layout检测 → 分子Layout检测 → 结果合并 → 最终输出
                ↓                    ↓           ↓
         普通blocks        分子/表格blocks   智能替换
```

## 新增组件

### 1. BlockTypes
- `Molecule`: 化学分子结构
- `MoleculeTable`: 包含分子数据的表格

### 2. Block类
- `Molecule`: 输出`<mol>...</mol>`标签
- `MoleculeTable`: 输出`<mol_table>...</mol_table>`标签

### 3. MoleculeLayoutBuilder
集成img2mol的`Parser_Processer`，负责：
- 调用分子检测模型
- 调用表格检测模型
- 执行智能替换逻辑

## 配置参数

### processor_config
传入`Parser_Processer`的配置参数：

```python
processor_config = {
    "device": "cuda",                    # 设备: "cuda" 或 "cpu"
    "with_mol_detect": True,             # 启用分子检测
    "with_table_detect": True,           # 启用表格检测
    "use_yolo_mol_model": True,          # 使用YOLO分子模型
    "use_yolo_table_model": True,        # 使用YOLO表格模型
    "use_yolo_table_model_v2": True,     # 使用YOLO表格模型v2
    "debug": False,                      # 调试模式
    "num_workers": 1,                    # 工作进程数
    "padding": 0                         # 图像填充
}
```

### 替换阈值
- `overlap_threshold`: 分子替换阈值，默认0.9 (90%)
- `table_overlap_threshold`: 表格替换阈值，默认0.9 (90%)

## 使用方法

### 基本用法

```python
from marker.converters.pdf import PdfConverter

# 配置分子识别
processor_config = {
    "device": "cuda",
    "with_mol_detect": True,
    "with_table_detect": True,
}

artifact_dict = {
    "processor_config": processor_config,
}

config = {
    "use_molecule_detection": True,
}

# 创建转换器
converter = PdfConverter(
    artifact_dict=artifact_dict,
    config=config
)

# 处理PDF
result = converter("chemistry_paper.pdf")
```

### 高级配置

```python
# 自定义替换阈值
processor_config = {
    "device": "cuda",
    "with_mol_detect": True,
    "with_table_detect": True,
    "debug": True,  # 启用调试
}

# 可以通过config调整阈值（如果需要的话）
config = {
    "use_molecule_detection": True,
    "use_llm": True,  # 同时启用LLM处理
}
```

## 替换逻辑

### 分子替换
- 检测到的分子区域与**任何类型**的原有block重叠度>90%时进行替换
- 保持原有的页面结构顺序

### 表格替换 
- 检测到的分子表格**只替换原有的Table类型**的block
- IOU>90%时进行替换
- 其他类型的block不会被表格替换

### 替换过程
1. 计算新检测block与现有block的重叠度
2. 标记需要替换的原有blocks
3. 在原位置插入新的分子/表格blocks
4. 从页面结构中移除被替换的blocks

## 输出格式

### 分子结构
```html
<mol>
    <!-- 分子结构内容 -->
</mol>
```

### 分子表格
```html
<mol_table>
    <!-- 表格内容 -->
</mol_table>
```

## 依赖要求

确保安装了img2mol的相关依赖：

```bash
# img2mol相关依赖
pip install torch torchvision
pip install ultralytics  # YOLO模型
pip install rdkit-pypi   # 化学计算
# ... 其他img2mol依赖
```

## 故障排除

### 常见问题

1. **ImportError: img2mol.processor not found**
   - 确保img2mol在Python路径中
   - 检查img2mol/processor.py文件存在

2. **CUDA内存不足**
   - 设置`device: "cpu"`使用CPU
   - 减少batch_size

3. **模型文件缺失**
   - 确保YOLO模型文件路径正确
   - 检查img2mol的模型配置

### 调试建议

1. 启用调试模式：`"debug": True`
2. 检查processor初始化日志
3. 验证输入图像格式

## 性能优化

1. **GPU使用**: 确保CUDA可用时使用GPU
2. **批处理**: 调整batch_size以平衡速度和内存
3. **模型缓存**: 预加载模型以避免重复初始化

## 扩展说明

如果需要进一步的分子内容识别（如SMILES生成），可以：

1. 在`Molecule`和`MoleculeTable`类中添加额外的处理方法
2. 创建专门的分子处理processor
3. 在后处理阶段进行分子结构识别

该集成框架为化学文档处理提供了强大的基础设施。 