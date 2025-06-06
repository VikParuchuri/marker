# 分子识别Extraction测试脚本使用说明

这些测试脚本用于测试marker_main的extraction功能，特别是集成了img2mol的分子识别功能。**现在支持Mock模式，可以在没有img2mol依赖的情况下快速测试分子标签生成！**

## 文件说明

1. **test_molecule_extraction.py** - 基础测试脚本，支持Mock模式
2. **test_molecule_extraction_enhanced.py** - 增强版测试脚本，推荐使用，支持Mock模式
3. **README_molecule_testing.md** - 本说明文档

## 🎭 Mock模式 vs 🔬 真实模式

### Mock模式（默认）
- ✅ **无需安装img2mol依赖**
- ✅ **快速测试**，几秒钟完成
- ✅ **固定输出**：`<mol>c1ccccc1</mol>` 和 `<mol_table>placeholder</mol_table>`
- ✅ **随机生成**分子位置和数量
- ✅ **智能转换**部分表格为分子表格
- 🎯 适合测试分子标签生成逻辑

### 真实模式
- 📚 需要安装完整的img2mol依赖
- ⚡ 需要GPU支持（推荐）
- 🎯 真实的分子检测和识别
- 🔍 实际的化学结构分析

## 快速开始

### 1. 环境准备

```bash
# 基础依赖（必需）
pip install -r requirements.txt

# img2mol依赖（仅真实模式需要）
# pip install img2mol依赖...
```

### 2. 准备测试PDF

找一个PDF文件（任何PDF都可以，Mock模式会自动生成分子内容）：

### 3. 运行测试

```bash
# 🎭 Mock模式测试（推荐，快速测试）
python test_molecule_extraction.py
python test_molecule_extraction_enhanced.py

# 🔬 真实模型测试（需要img2mol）
python test_molecule_extraction.py --real
python test_molecule_extraction_enhanced.py --real

# 📊 综合测试
python test_molecule_extraction_enhanced.py --comprehensive
python test_molecule_extraction_enhanced.py --comprehensive --real
```

## 测试输出

### Mock模式输出示例
```
🎭 运行模式: Mock测试模式 (快速测试)
   - 将生成假的分子检测数据
   - 输出固定内容: <mol>c1ccccc1</mol> 和 <mol_table>placeholder</mol_table>
   - 不需要img2mol依赖

📄 页面 1: Mock生成 3 个分子, 1 个分子表格
📄 页面 2: Mock生成 2 个分子, 0 个分子表格

📊 提取结果分析:
  - 分子结构数量: 5
  - 分子表格数量: 1
  - 文本中<mol>标签: 5
  - 文本中<mol_table>标签: 1
```

### 生成的文件
1. **Markdown文件** - 包含分子标签的转换结果
   ```
   {doc_id}_enhanced_molecules.md
   ```

2. **元数据文件** - 详细的处理统计信息
   ```
   {doc_id}_enhanced_metadata.json
   ```

3. **配置文件** - 使用的配置参数
   ```
   {doc_id}_config.json
   ```

## 分子标签说明

### Mock模式输出
- `<mol>c1ccccc1</mol>` - 苯环的SMILES表示
- `<mol_table>placeholder</mol_table>` - 分子表格占位符

### 真实模式输出
- `<mol>实际的分子结构</mol>` - 检测到的真实分子结构
- `<mol_table>表格内容</mol_table>` - 检测到的分子表格内容

## 配置选项

### Mock模式配置
```python
processor_config = {
    'use_mock_data': True,        # 启用Mock模式
    'mock_mode': True,            # 别名
    'debug': True,                # 调试输出
    # 其他配置在Mock模式下会被忽略
}
```

### 真实模式配置
```python
processor_config = {
    'use_mock_data': False,       # 禁用Mock模式
    'device': 'cuda',             # 设备：'cuda' 或 'cpu'
    'with_mol_detect': True,      # 启用分子检测
    'with_table_detect': True,    # 启用表格检测
    'use_yolo_mol_model': True,   # 使用YOLO分子模型
    'use_yolo_table_model': True, # 使用YOLO表格模型
    'debug': True,                # 调试模式
    'num_workers': 1,             # 工作线程数
    # 更多img2mol配置...
}
```

## 常见问题

### 1. Mock模式相关

**Q: Mock模式生成的分子数量是固定的吗？**
A: 不是，每页随机生成2-4个分子，30-50%的表格会被转换为分子表格。

**Q: 可以自定义Mock输出内容吗？**
A: 目前输出固定的`c1ccccc1`（苯环）和`placeholder`，可以修改代码中的mock数据。

**Q: Mock模式会替换真实的表格吗？**
A: 是的，Mock模式会智能地将部分检测到的表格转换为分子表格，演示替换逻辑。

### 2. 模式切换

**Q: 如何在代码中控制使用哪种模式？**
A: 通过命令行参数：默认Mock模式，使用`--real`启用真实模式。

**Q: 可以在同一次运行中测试两种模式吗？**
A: 需要分别运行，但可以使用综合测试脚本依次测试。

### 3. 性能对比

| 特性 | Mock模式 | 真实模式 |
|------|----------|----------|
| 速度 | 🚀 极快（秒级） | ⏳ 较慢（分钟级） |
| 依赖 | 📦 少 | 📚 多 |
| 准确性 | 🎭 模拟 | 🔬 真实 |
| 用途 | 🧪 功能测试 | 🎯 实际应用 |

## 故障排除

### Mock模式问题
1. **没有生成分子标签** - 检查PDF是否有内容，Mock模式需要页面结构
2. **Mock模式失效** - 检查`use_mock_data`配置是否正确传递

### 真实模式问题
1. **模型加载失败** - 检查img2mol依赖和模型文件
2. **GPU内存不足** - 切换到CPU模式或减少工作线程

### 通用问题
1. **PDF文件无法读取** - 确保路径正确且文件存在
2. **输出目录权限** - 确保有写权限

## 开发建议

1. **🎭 先用Mock模式测试** - 验证基础功能和标签生成
2. **🔬 再用真实模式验证** - 确认实际分子检测效果
3. **📊 使用综合测试** - 批量测试不同配置
4. **🐛 调试时启用debug** - 获取详细日志

## 示例脚本

```bash
# 快速验证功能
python test_molecule_extraction_enhanced.py

# 完整测试流程
python test_molecule_extraction_enhanced.py --comprehensive

# 真实模型测试
python test_molecule_extraction_enhanced.py --real

# 查看帮助
python test_molecule_extraction_enhanced.py --help
```

## 联系支持

如果测试脚本无法正常工作，请提供：
- 错误信息完整日志
- 使用的PDF文件类型和大小
- 系统配置（GPU/CPU，内存等）
- Python环境信息 