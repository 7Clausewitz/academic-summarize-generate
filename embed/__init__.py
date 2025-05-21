"""
文本分析与相似度检索工具包

这个包提供了从XML文件中提取文本、生成嵌入向量并进行相似度检索的功能。
包含四个主要模块：
- xml_text_extractor: XML文本提取工具
- text_similarity: 文本相似度检索工具
- text_processor: 集成模块，整合提取和检索功能
- abstract_extractor: 摘要和标题提取与检索工具
"""

__version__ = "0.1.0"
__author__ = "AI Assistant"

# 模块导出
from .xml_text_extractor import (
    extract_paragraphs_with_metadata,
    process_directory_with_metadata
)

from .text_similarity import (
    load_embeddings,
    create_query_embedding,
    search_similar_text,
    search_by_text,
    search_by_existing_text,
    format_search_results
)

from .text_processor import (
    extract_and_create_embeddings,
    process_and_search,
    initialize_api_client
)

# 导出摘要和标题提取功能
from .abstract_extractor import (
    extract_title_from_file,
    extract_abstract_from_file,
    extract_info_from_file,
    process_directory,
    create_embeddings_from_info,
    search_by_text as search_by_abstract_text,
    process_and_search as process_and_search_abstracts,
    format_article_results
)

# 设置日志输出（可选）
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 导出的函数和类列表
__all__ = [
    # xml_text_extractor
    "extract_paragraphs_with_metadata",
    "process_directory_with_metadata",
    
    # text_similarity
    "load_embeddings",
    "create_query_embedding",
    "search_similar_text",
    "search_by_text",
    "search_by_existing_text",
    "format_search_results",
    
    # text_processor
    "extract_and_create_embeddings",
    "process_and_search",
    "initialize_api_client",
    
    # abstract_extractor
    "extract_title_from_file",
    "extract_abstract_from_file",
    "extract_info_from_file",
    "process_directory",
    "create_embeddings_from_info",
    "search_by_abstract_text",
    "process_and_search_abstracts",
    "format_article_results"
] 