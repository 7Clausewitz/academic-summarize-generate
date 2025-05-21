# 文本分析与相似度检索工具

本工具集提供了从XML文件中提取文本、生成嵌入向量并进行相似度检索的功能。主要包含三个模块：

1. `xml_text_extractor.py` - XML文本提取工具
2. `text_similarity.py` - 文本相似度检索工具
3. `text_processor.py` - 集成模块，整合提取和检索功能

## 功能概览

- 从XML文件中提取段落文本及其元数据
- 生成文本的嵌入向量（需要嵌入API）
- 基于嵌入向量计算文本相似度
- 根据查询文本搜索最相似的内容
- 交互式界面，方便用户操作

## 安装依赖

```bash
# 安装必要的依赖项
pip install numpy volcenginesdkarkruntime
```

## 环境配置

### 方式1：使用环境变量
```bash
# Linux/Mac设置环境变量
export DOUBAO_API_KEY="你的API密钥"

# Windows下使用
set DOUBAO_API_KEY="你的API密钥"
```

### 方式2：使用.env文件（推荐）
在embed目录下创建`.env`文件，内容如下：

```
# API密钥配置
DOUBAO_API_KEY=你的API密钥
ARK_API_KEY=你的API密钥     # 与DOUBAO_API_KEY相同

# 模型和批处理配置
EMBEDDING_MODEL=doubao-embedding-text-240715
BATCH_SIZE=10

# 可选：自定义API基础URL
# ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

## 使用方法

### 0. 统一入口点

推荐使用统一入口点脚本`run.py`来运行各个功能模块：

```bash
# 运行XML提取功能
python -m embed.run extract --input example.xml --output paragraphs.json

# 运行相似度搜索功能
python -m embed.run search --embeddings embeddings.json --query "你的查询文本"

# 运行一站式处理功能
python -m embed.run process --input ./data/ --query "你的查询文本"

# 启动交互式界面
python -m embed.run process --interactive
```

### 1. XML文本提取

提取XML文件中的段落文本：

```bash
python -m embed.xml_text_extractor --input example.xml --output paragraphs.json
```

处理整个目录中的XML文件：

```bash
python -m embed.xml_text_extractor --input ./data/ --pattern "*.xml" --output all_paragraphs.json
```

### 2. 文本相似度检索

基于现有嵌入向量文件搜索相似文本：

```bash
python -m embed.text_similarity --embeddings embeddings.json --query "你的查询文本" --top-k 5 --threshold 0.6
```

启动交互式搜索界面：

```bash
python -m embed.text_similarity --embeddings embeddings.json --interactive
```

### 3. 集成处理

一站式处理（提取、生成嵌入向量、搜索）：

```bash
python -m embed.text_processor process --input ./data/ --query "你的查询文本" --embeddings result.json
```

启动交互式界面：

```bash
python -m embed.text_processor --interactive
```

## 模块说明

### `xml_text_extractor.py`

该模块专注于从XML文件中提取文本内容，特别是段落文本，并保留相关元数据。

主要函数：
- `extract_paragraphs_with_metadata()` - 从单个XML文件中提取段落和元数据
- `process_directory_with_metadata()` - 处理整个目录中的XML文件

### `text_similarity.py`

该模块提供基于嵌入向量的文本相似度计算和检索功能。

主要函数：
- `load_embeddings()` - 加载嵌入向量数据
- `search_similar_text()` - 搜索相似文本
- `search_by_text()` - 基于查询文本搜索
- `search_by_existing_text()` - 基于现有文本搜索

### `text_processor.py`

该模块整合了提取和检索功能，提供一站式处理解决方案。

主要函数：
- `extract_and_create_embeddings()` - 提取文本并生成嵌入向量
- `process_and_search()` - 一站式提取、生成和搜索
- `interactive()` - 交互式用户界面

## 示例工作流程

1. 从XML文件提取文本并生成嵌入向量：
   ```bash
   python -m embed.text_processor extract --input data/articles/ --output embeddings.json
   ```

2. 使用嵌入向量搜索相似文本：
   ```bash
   python -m embed.text_processor search --embeddings embeddings.json --query "人工智能应用"
   ```

3. 保存搜索结果：
   ```bash
   # 在交互式界面中选择保存选项
   python -m embed.text_processor --interactive
   ```

## 作为Python包使用

你也可以将embed作为Python包导入到你的项目中：

```python
# 导入需要的函数
from embed import extract_paragraphs_with_metadata, search_similar_text, process_and_search

# 使用函数
paragraphs = extract_paragraphs_with_metadata("example.xml")
```

## 注意事项

- 使用嵌入API功能需要有效的API密钥
- 大型文件或大量文本处理可能需要较长时间
- 相似度阈值(0-1)影响搜索结果质量，建议从0.5开始调整
- 如遇导入错误，请确保使用`-m`方式运行模块或使用提供的入口点 