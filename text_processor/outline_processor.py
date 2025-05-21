#!/usr/bin/env python3
"""
大纲处理与文献检索集成模块：
1. 处理用户输入的大纲
2. 使用outline_decompose.py将大纲分解为多个板块
3. 对每个板块提取关键词，在摘要和正文数据库中检索相关内容
4. 将结果汇总为结构化数据
"""

import os
import sys
import json
import logging
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from volcenginesdkarkruntime import Ark
import numpy as np
import glob
import time

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("outline_processor")

# 添加相关模块路径
current_dir = Path(__file__).parent.absolute()
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# 添加outline_decompose目录
outline_dir = os.path.join(parent_dir, "outline_decompose")
if outline_dir not in sys.path:
    sys.path.append(str(outline_dir))

# 添加embed目录
embed_dir = os.path.join(parent_dir, "embed")
if embed_dir not in sys.path:
    sys.path.append(str(embed_dir))

# 尝试导入相关模块
try:
    from outline_decompose.outline_decompose import OutlineDecomposer
    from embed.text_processor import initialize_api_client,extract_and_create_embeddings
    from embed.abstract_extractor import search_by_text, search_by_text as search_abstract_by_text
except ImportError as e:
    logger.error(f"导入模块出错: {e}")
    logger.error("请确保已安装所有必要的依赖和模块")
    sys.exit(1)

def clean_for_json(obj):
    """
    清理对象，使其可以序列化为JSON
    
    参数:
        obj: 任意Python对象
        
    返回:
        可序列化的对象
    """
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, tuple):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.int64) or isinstance(obj, np.int32):
        return int(obj)
    elif isinstance(obj, np.float64) or isinstance(obj, np.float32):
        return float(obj)
    else:
        return obj

class OutlineProcessor:
    """大纲处理与文献检索的集成处理器"""
    
    def __init__(self):
        """初始化处理器"""
        # 检查API密钥
        self.api_key = os.getenv('ARK_API_KEY')
        if not self.api_key:
            logger.error("环境变量ARK_API_KEY未设置")
            raise ValueError("请设置环境变量ARK_API_KEY")
        
        # 初始化API客户端
        self.api_client = initialize_api_client()
        if not self.api_client:
            logger.error("API客户端初始化失败")
            raise ValueError("API客户端初始化失败")
        
        # 初始化大纲分解器
        self.outline_decomposer = OutlineDecomposer(self.api_key)
        
        # 初始化Ark客户端（用于调用大模型）
        self.client = Ark(api_key=self.api_key)
        self.model = "doubao-1-5-thinking-pro-250415"
        
        # 设置嵌入向量文件路径
        self.embeddings_dir = os.path.join(current_dir, "embeddings")
        self.abstract_embeddings_file = os.path.join(self.embeddings_dir, "abstract_embeddings.json")
        self.fulltext_embeddings_file = os.path.join(self.embeddings_dir, "fulltext_embeddings.json")
        
        # 检查嵌入向量文件
        if not os.path.exists(self.abstract_embeddings_file):
            logger.warning(f"摘要嵌入向量文件不存在: {self.abstract_embeddings_file}")
        if not os.path.exists(self.fulltext_embeddings_file):
            logger.warning(f"正文嵌入向量文件不存在: {self.fulltext_embeddings_file}")
        
        # 设置输出目录
        self.output_dir = os.path.join(current_dir, "outline_results")
        os.makedirs(self.output_dir, exist_ok=True)



    
    def decompose_outline(self, outline_text):
        """
        分解大纲为多个板块
        
        参数:
            outline_text: 大纲文本
            
        返回:
            dict: 分解后的大纲JSON对象
        """
        logger.info("开始分解大纲...")
        try:
            result = self.outline_decomposer.decompose_outline(outline_text)
            logger.info(f"大纲分解完成，共 {len(result.get('blocks', []))} 个板块")
            return result
        except Exception as e:
            logger.error(f"大纲分解失败: {e}")
            raise
    
    def search_abstract_by_keywords(self, keywords, top_k=5):
        """
        使用关键词在摘要数据库中搜索
        
        参数:
            keywords: 关键词列表
            top_k: 每个关键词返回的结果数量
            
        返回:
            list: 搜索结果列表，每个关键词保留top_k个结果
        """
        # 确保keywords不为None
        if not keywords:
            logger.warning("关键词列表为空，无法进行摘要搜索")
            return []
        
        if not os.path.exists(self.abstract_embeddings_file):
            logger.warning(f"摘要嵌入向量文件不存在: {self.abstract_embeddings_file}，将返回空结果")
            return []
            
        if not os.path.getsize(self.abstract_embeddings_file):
            logger.warning(f"摘要嵌入向量文件为空: {self.abstract_embeddings_file}，将返回空结果")
            return []
        
        all_results = []
        keyword_results = {}  # 用于存储每个关键词的搜索结果
        
        for keyword in keywords:
            if not keyword:  # 跳过空关键词
                continue
            
            logger.info(f"使用关键词在摘要数据库中搜索: {keyword}")
            try:
                results = search_abstract_by_text(
                    keyword, 
                    self.abstract_embeddings_file,
                    self.api_client,
                    top_k=top_k,
                    threshold=0.1  # 设置较低的阈值以确保返回结果
                )
                
                if results:
                    # 为每个结果添加来源关键词信息
                    for result in results:
                        result["source_keyword"] = keyword
                        
                    # 存储该关键词的结果
                    keyword_results[keyword] = results
                    
                    # 同时将结果添加到所有结果列表
                    all_results.extend(results)
                    logger.info(f"找到 {len(results)} 条摘要搜索结果")
                else:
                    logger.info(f"未找到关键词 '{keyword}' 的摘要搜索结果")
                    keyword_results[keyword] = []
            except Exception as e:
                logger.error(f"摘要搜索出错: {e}")
                keyword_results[keyword] = []
                # 继续处理下一个关键词，不中断整个搜索过程
        
        # 执行去重（基于完整文本内容）
        try:
            # 首先，对所有结果进行去重，相同text值只保留一个结果
            unique_results_by_text = {}  # 使用text作为键的字典
            
            # 记录每个text来自哪些关键词
            text_sources = {}  # 记录每个text对应的所有来源关键词
            
            for result in all_results:
                text = result.get("text", "")
                if not text:
                    continue
                    
                # 记录文本来源的关键词
                if text not in text_sources:
                    text_sources[text] = set()
                text_sources[text].add(result.get("source_keyword", ""))
                
                # 保存相似度最高的结果
                if text not in unique_results_by_text or result.get("similarity", 0) > unique_results_by_text[text].get("similarity", 0):
                    unique_results_by_text[text] = result.copy()
            
            # 更新每个结果的来源关键词列表
            for text, result in unique_results_by_text.items():
                if text in text_sources:
                    result["source_keywords"] = list(text_sources[text])  # 所有来源关键词列表
            
            # 转换为列表并按相似度降序排序
            unique_results_list = list(unique_results_by_text.values())
            unique_results_list.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            
            # 记录去重前后的数量变化
            logger.info(f"摘要搜索去重: 从 {len(all_results)} 条结果去重为 {len(unique_results_list)} 条唯一结果")
            
            # 返回前top_k×len(keywords)个结果，确保有足够的结果
            max_results = min(top_k * len(keywords), len(unique_results_list))
            return unique_results_list[:max_results]
            
        except Exception as e:
            logger.error(f"处理摘要搜索结果时出错: {e}")
            return []  # 发生错误时返回空结果
    
    def generate_enhanced_keywords(self, block, abstract_results):
        """
        调用大模型生成增强的关键词
        
        参数:
            block: 大纲板块信息
            abstract_results: 摘要搜索结果
            
        返回:
            list: 生成的关键词列表
        """
        # 确保block不为None
        if not block:
            logger.warning("板块信息为空，无法生成增强关键词")
            return []
        
        # 准备大纲信息
        outline_text = f"标题: {block.get('title', '')}\n内容: {block.get('content', '')}"
        
        # 准备摘要信息
        abstracts_text = ""
        if abstract_results:
            for i, result in enumerate(abstract_results, 1):
                title = result.get("title", "无标题")
                abstract = result.get("abstract", "无摘要")
                abstracts_text += f"[文献{i}] 标题: {title}\n摘要: {abstract}\n\n"
        
        if not abstracts_text:
            abstracts_text = "未找到相关文献摘要。请根据大纲内容自行生成关键词。"
        
        # 构建提示词
        prompt = f"""
你的任务是根据提供的一小节综述大纲和搜索的文献的摘要信息，思考大纲书写应当包含的内容，找出对于文章的逻辑至关重要的信息以及重要的专业术语信息，最后输出最想检索的关键字，以json格式呈现。

首先，请仔细阅读以下一小节综述大纲：
<outline>
{outline_text}
</outline>

接着，请仔细阅读以下搜索的文献的摘要信息：
<literature_abstract>
{abstracts_text}
</literature_abstract>

在思考大纲书写应包含的内容时，需结合大纲和文献摘要，分析大纲所涉及主题的核心要素、关联要点等。
对于确定对文章逻辑至关重要的信息，要考虑哪些信息是构建文章逻辑框架必不可少的；确定重要专业术语信息时，需找出在大纲和文献摘要中具有专业含义且对理解主题有重要作用的词汇。

以json格式输出你最想检索的关键词，最多不超过10个关键词。关键词用英文输出。
{{
  "keywords": []
}}
"""
        
        logger.info("调用大模型生成增强关键词...")
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ]
            )
            
            response = completion.choices[0].message.content
            import re
            response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            logger.info("大模型返回完成")
            
            # 尝试解析JSON响应
            try:
                # 查找JSON内容的开始和结束
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = response[json_start:json_end]
                    result = json.loads(json_content)
                    keywords = result.get("keywords", [])
                    logger.info(f"生成了 {len(keywords)} 个增强关键词")
                    return keywords
                else:
                    logger.error("无法在响应中找到有效的JSON，尝试提取关键词")
                    # 尝试从原始响应中提取关键词
                    words = re.findall(r'"([^"]+)"', response)
                    if words:
                        logger.info(f"从原始响应中提取了 {len(words)} 个关键词")
                        return words[:10]  # 最多返回10个关键词
                    else:
                        # 使用原始大纲关键词
                        original_keywords = block.get("keywords", [])
                        logger.info(f"使用原始关键词: {original_keywords}")
                        return original_keywords
            except json.JSONDecodeError:
                logger.error(f"JSON解析错误，原始响应: {response}")
                # 尝试从原始响应中提取关键词
                words = re.findall(r'"([^"]+)"', response)
                if words:
                    logger.info(f"从原始响应中提取了 {len(words)} 个关键词")
                    return words[:10]  # 最多返回10个关键词
                else:
                    # 使用原始大纲关键词
                    original_keywords = block.get("keywords", [])
                    logger.info(f"使用原始关键词: {original_keywords}")
                    return original_keywords
                
        except Exception as e:
            logger.error(f"调用大模型出错: {e}")
            # 使用原始大纲关键词
            original_keywords = block.get("keywords", [])
            logger.info(f"使用原始关键词: {original_keywords}")
            return original_keywords
    
    def search_fulltext_by_keywords(self, keywords, top_k=5):
        """
        使用关键词在正文数据库中搜索
        
        参数:
            keywords: 关键词列表
            top_k: 每个关键词返回的结果数量
            
        返回:
            list: 搜索结果列表，每个关键词保留top_k个结果
        """
        # 确保keywords不为None
        if not keywords:
            logger.warning("关键词列表为空，无法进行正文搜索")
            return []
        
        if not os.path.exists(self.fulltext_embeddings_file):
            logger.warning(f"正文嵌入向量文件不存在: {self.fulltext_embeddings_file}，将返回空结果")
            return []
            
        if not os.path.getsize(self.fulltext_embeddings_file):
            logger.warning(f"正文嵌入向量文件为空: {self.fulltext_embeddings_file}，将返回空结果")
            return []
        
        all_results = []
        keyword_results = {}  # 用于存储每个关键词的搜索结果
        
        for keyword in keywords:
            if not keyword:  # 跳过空关键词
                continue
            
            logger.info(f"使用关键词在正文数据库中搜索: {keyword}")
            try:
                results = search_by_text(
                    keyword, 
                    self.fulltext_embeddings_file,
                    self.api_client,
                    top_k=top_k,
                    threshold=0.2  # 设置较低的阈值以确保返回结果
                )
                
                if results:
                    # 为每个结果添加来源关键词信息
                    for result in results:
                        result["source_keyword"] = keyword
                        
                    # 存储该关键词的结果
                    keyword_results[keyword] = results
                    
                    # 同时将结果添加到所有结果列表
                    all_results.extend(results)
                    logger.info(f"找到 {len(results)} 条正文搜索结果")
                else:
                    logger.info(f"未找到关键词 '{keyword}' 的正文搜索结果")
                    keyword_results[keyword] = []
            except Exception as e:
                logger.error(f"正文搜索出错: {e}")
                keyword_results[keyword] = []
                # 继续处理下一个关键词，不中断整个搜索过程
        
        # 去重（基于完整文本内容）
        try:
            # 首先，对所有结果进行去重，相同text值只保留一个结果
            unique_results_by_text = {}  # 使用text作为键的字典
            
            # 记录每个text来自哪些关键词
            text_sources = {}  # 记录每个text对应的所有来源关键词
            
            for result in all_results:
                text = result.get("text", "")
                if not text:
                    continue
                    
                # 记录文本来源的关键词
                if text not in text_sources:
                    text_sources[text] = set()
                text_sources[text].add(result.get("source_keyword", ""))
                
                # 保存相似度最高的结果
                if text not in unique_results_by_text or result.get("similarity", 0) > unique_results_by_text[text].get("similarity", 0):
                    unique_results_by_text[text] = result.copy()
            
            # 更新每个结果的来源关键词列表
            for text, result in unique_results_by_text.items():
                if text in text_sources:
                    result["source_keywords"] = list(text_sources[text])  # 所有来源关键词列表
            
            # 转换为列表并按相似度降序排序
            unique_results_list = list(unique_results_by_text.values())
            unique_results_list.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            
            # 记录去重前后的数量变化
            logger.info(f"正文搜索去重: 从 {len(all_results)} 条结果去重为 {len(unique_results_list)} 条唯一结果")
            
            # 返回前top_k×len(keywords)个结果，确保有足够的结果
            max_results = min(top_k * len(keywords), len(unique_results_list))
            return unique_results_list[:max_results]
            
        except Exception as e:
            logger.error(f"处理正文搜索结果时出错: {e}")
            return []  # 发生错误时返回空结果


    def process_outline_block(self, block, block_index):
        """
        处理单个大纲板块
        
        参数:
            block: 板块信息字典
            block_index: 板块索引
            
        返回:
            dict: 处理结果字典
        """
        logger.info(f"开始处理板块 {block_index+1}: {block.get('title', '')}")
        
        # 1. 提取板块原始关键词
        original_keywords = block.get("keywords", [])
        if not original_keywords:
            logger.warning(f"板块 {block_index+1} 没有原始关键词")
            original_keywords = []
        logger.info(f"板块原始关键词: {original_keywords}")
        
        # 2. 使用关键词在摘要数据库中搜索
        try:
            abstract_results = self.search_abstract_by_keywords(original_keywords)
        except Exception as e:
            logger.error(f"摘要搜索过程出错: {e}")
            abstract_results = []
        
        # 3. 调用大模型生成增强关键词
        try:
            enhanced_keywords = self.generate_enhanced_keywords(block, abstract_results)
        except Exception as e:
            logger.error(f"生成增强关键词出错: {e}")
            enhanced_keywords = original_keywords.copy()  # 使用原始关键词
        
        # 4. 使用增强关键词在正文数据库中搜索
        try:
            fulltext_results = self.search_fulltext_by_keywords(enhanced_keywords)
        except Exception as e:
            logger.error(f"正文搜索过程出错: {e}")
            fulltext_results = []
        
        # 5. 整合结果
        result = {
            "block_index": block_index,
            "block_info": block,
            "original_keywords": original_keywords,
            "enhanced_keywords": enhanced_keywords,
            "abstract_results": abstract_results,
            "fulltext_results": fulltext_results
        }
        
        # 清理结果，确保可序列化
        result = clean_for_json(result)
        
        # 保存单个板块的处理结果
        try:
            block_output_file = os.path.join(self.output_dir, f"block_{block_index+1}.json")
            with open(block_output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"板块 {block_index+1} 处理结果已保存到: {block_output_file}")
        except Exception as e:
            logger.error(f"保存板块 {block_index+1} 处理结果时出错: {e}")
        
        return result
    
    def process_outline(self, outline_text, auto_generate_review=False):
        """
        处理整个大纲
        
        参数:
            outline_text: 大纲文本
            auto_generate_review: 是否自动生成综述内容
            
        返回:
            str: 最终结果文件路径，或生成的综述文件路径
        """
        # 1. 分解大纲
        outline_result = self.decompose_outline(outline_text)
        blocks = outline_result.get("blocks", [])
        
        if not blocks:
            logger.error("大纲分解没有产生有效的板块")
            raise ValueError("大纲分解失败")
        
        # 2. 保存分解结果
        outline_file = os.path.join(self.output_dir, "outline_decomposed.json")
        with open(outline_file, 'w', encoding='utf-8') as f:
            json.dump(outline_result, f, ensure_ascii=False, indent=2)
        logger.info(f"大纲分解结果已保存到: {outline_file}")
        
        # 3. 逐个处理板块
        all_results = []
        for i, block in enumerate(blocks):
            block_result = self.process_outline_block(block, i)
            all_results.append(block_result)
        
        # 4. 整合所有板块结果
        final_result = {
            "outline": outline_text,
            "blocks_count": len(blocks),
            "blocks_results": all_results
        }
        
        # 5. 保存最终结果
        timestamp = os.path.basename(self.output_dir)
        final_file = os.path.join(self.output_dir, f"final_result_{timestamp}.json")
        with open(final_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2)
        logger.info(f"最终处理结果已保存到: {final_file}")
        
        # 6. 如果需要自动生成综述
        if auto_generate_review:
            logger.info("开始自动生成综述...")
            review_file = self.generate_review()
            logger.info(f"综述生成完成，结果保存在: {review_file}")
            return review_file
        
        return final_file
    
    def generate_review(self, json_dir=None, output_dir=None, merge_output=True):
        """
        使用大模型API为每个block生成内容，并合并为完整综述
        
        参数:
            json_dir: 包含block_*.json文件的目录，默认为self.output_dir
            output_dir: 生成结果的输出目录，默认为self.output_dir下的reviews子目录
            merge_output: 是否将所有生成结果合并为一个文件
        
        返回:
            str: 最终生成的综述文件路径
        """
        # 设置默认目录
        if json_dir is None:
            json_dir = self.output_dir
            
        if output_dir is None:
            output_dir = os.path.join(self.output_dir, "reviews")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 查找所有block_*.json文件
        block_files = sorted(glob.glob(os.path.join(json_dir, "block_*.json")), 
                           key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
        
        if not block_files:
            logger.error(f"在目录 {json_dir} 中没有找到block_*.json文件")
            return None
        
        logger.info(f"找到 {len(block_files)} 个block文件，准备生成内容")
        
        # 逐个处理block文件
        all_contents = []
        
        for i, block_file in enumerate(block_files):
            block_num = i + 1
            logger.info(f"处理 block {block_num}/{len(block_files)}: {os.path.basename(block_file)}")
            
            try:
                # 读取block文件
                with open(block_file, 'r', encoding='utf-8') as f:
                    block_data = json.load(f)
                
                # 提取信息
                block_info = block_data.get("block_info", {})
                title = block_info.get("title", f"Section {block_num}")
                content = block_info.get("content", "")
                
                # 收集相关文献内容
                abstract_results = block_data.get("abstract_results", [])
                fulltext_results = block_data.get("fulltext_results", [])
                
                # 构建提示词
                references = []
                for j, result in enumerate(abstract_results + fulltext_results):
                    text = result.get("text", "")
                    if text:
                        similarity = result.get("similarity", 0)
                        references.append(f"参考文献 {j+1} [相似度: {similarity:.2f}]:\n{text}\n")
                
                references_text = "\n".join(references[:15])  # 最多包含15条参考文献
                
                prompt = f"""
请你根据以下大纲和参考文献内容，撰写一篇学术综述的一部分。

【大纲部分】：
标题：{title}
内容：{content}

【相关参考文献】：
{references_text}

请根据以上内容写一段关于"{title}"的综述文章内容。要求：
1. 使用学术论文风格，语言严谨、客观
2. 内容应当完整、连贯，与给定大纲主题紧密相关
3. 适当引用参考文献中的观点和发现，但不要直接复制
4. 生成内容应当在800-1500字之间
5. 不需要包含引用标记，直接融入文本中
6. 不需要引言和结论部分，直接开始正文内容

请直接给出这部分综述的文本内容，无需其他解释。
"""
                
                # 调用大模型API
                logger.info(f"为 block {block_num} 生成内容...")
                
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt},
                    ]
                )
                
                generated_content = completion.choices[0].message.content
                
                # 保存单个block的内容
                block_output_file = os.path.join(output_dir, f"block_{block_num}_review.txt")
                with open(block_output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n")
                    f.write(generated_content)
                
                logger.info(f"Block {block_num} 内容已保存至: {block_output_file}")
                
                # 添加到合并内容中
                all_contents.append({
                    "title": title,
                    "content": generated_content
                })
                
            except Exception as e:
                logger.error(f"处理 block {block_num} 时出错: {str(e)}")
        
        # 如果需要合并输出
        if merge_output and all_contents:
            # 创建一个完整的综述
            merged_content = ""
            
            for item in all_contents:
                merged_content += f"# {item['title']}\n\n"
                merged_content += f"{item['content']}\n\n"
            
            # 生成输出文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            merged_file = os.path.join(output_dir, f"complete_review_{timestamp}.md")
            
            # 保存完整综述
            with open(merged_file, 'w', encoding='utf-8') as f:
                f.write(merged_content)
            
            logger.info(f"完整综述已保存至: {merged_file}")
            return merged_file
        
        return output_dir


class OutlineProcessorApp:
    """大纲处理应用程序界面"""
    
    def __init__(self, root):
        """初始化应用程序界面"""
        self.root = root
        self.root.title("大纲处理与文献检索工具")
        self.root.geometry("900x700")
        
        self.create_widgets()
        
        # 尝试初始化处理器
        try:
            self.processor = OutlineProcessor()
            self.status_var.set("就绪")
        except Exception as e:
            messagebox.showerror("初始化错误", f"处理器初始化失败: {str(e)}")
            self.status_var.set("初始化失败")
            self.process_button.config(state=tk.DISABLED)
    
    def create_widgets(self):
        """创建界面组件"""
        # 输入区域
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(input_frame, text="请输入要处理的大纲:").pack(anchor="w")
        
        self.outline_input = scrolledtext.ScrolledText(input_frame, height=10)
        self.outline_input.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 按钮
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)
        
        self.process_button = tk.Button(button_frame, text="处理大纲", command=self.process_outline)
        self.process_button.pack(side=tk.LEFT, padx=5)
        
        self.generate_review_button = tk.Button(button_frame, text="生成综述", command=self.generate_review)
        self.generate_review_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = tk.Button(button_frame, text="清空", command=self.clear_input)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        self.load_button = tk.Button(button_frame, text="加载大纲文件", command=self.load_outline)
        self.load_button.pack(side=tk.LEFT, padx=5)
        
        # 选项框架
        options_frame = tk.Frame(self.root)
        options_frame.pack(pady=5)
        
        # 自动生成综述选项
        self.auto_generate_var = tk.BooleanVar(value=False)
        self.auto_generate_check = tk.Checkbutton(
            options_frame, 
            text="处理完成后自动生成综述", 
            variable=self.auto_generate_var
        )
        self.auto_generate_check.pack(side=tk.LEFT, padx=5)
        
        # 输出区域
        output_frame = tk.Frame(self.root)
        output_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(output_frame, text="处理日志:").pack(anchor="w")
        
        self.log_output = scrolledtext.ScrolledText(output_frame, height=15)
        self.log_output.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 自定义日志处理器
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
            
            def emit(self, record):
                msg = self.format(record)
                def append():
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n')
                    self.text_widget.configure(state='disabled')
                    self.text_widget.yview(tk.END)
                self.text_widget.after(0, append)
        
        # 配置日志输出到界面
        text_handler = TextHandler(self.log_output)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("初始化中...")
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def process_outline(self):
        """处理大纲"""
        outline_text = self.outline_input.get("1.0", tk.END).strip()
        if not outline_text:
            messagebox.showwarning("警告", "请输入大纲内容")
            return
        
        self.process_button.config(state=tk.DISABLED)
        self.generate_review_button.config(state=tk.DISABLED)
        self.status_var.set("处理中...")
        self.root.update()
        
        # 获取是否自动生成综述的选项
        auto_generate_review = self.auto_generate_var.get()
        
        # 创建处理线程
        def process_thread():
            try:
                result_file = self.processor.process_outline(outline_text, auto_generate_review)
                self.root.after(0, lambda: self.process_complete(result_file))
            except Exception as e:
                logger.error(f"处理失败: {e}")
                self.root.after(0, lambda: self.process_failed(str(e)))
        
        import threading
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()
    
    def process_complete(self, result_file):
        """处理完成"""
        self.status_var.set("处理完成")
        self.process_button.config(state=tk.NORMAL)
        self.generate_review_button.config(state=tk.NORMAL)
        messagebox.showinfo("成功", f"大纲处理完成！\n结果已保存到: {result_file}")
    
    def process_failed(self, error_msg):
        """处理失败"""
        self.status_var.set("处理失败")
        self.process_button.config(state=tk.NORMAL)
        self.generate_review_button.config(state=tk.NORMAL)
        messagebox.showerror("错误", f"处理失败: {error_msg}")
    
    def clear_input(self):
        """清空输入"""
        self.outline_input.delete("1.0", tk.END)
        
    def load_outline(self):
        """加载大纲文件"""
        file_path = filedialog.askopenfilename(
            title="选择大纲文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.outline_input.delete("1.0", tk.END)
                    self.outline_input.insert(tk.END, content)
            except Exception as e:
                messagebox.showerror("错误", f"无法读取文件: {str(e)}")
    
    def generate_review(self):
        """生成综述"""
        # 检查是否已有处理结果
        if not hasattr(self.processor, 'output_dir') or not self.processor.output_dir:
            messagebox.showwarning("警告", "请先处理大纲才能生成综述")
            return
            
        self.process_button.config(state=tk.DISABLED)
        self.generate_review_button.config(state=tk.DISABLED)
        self.status_var.set("正在生成综述...")
        self.root.update()
        
        # 创建生成线程
        def generate_thread():
            try:
                result_file = self.processor.generate_review()
                if result_file:
                    self.root.after(0, lambda: self.generation_complete(result_file))
                else:
                    self.root.after(0, lambda: self.process_failed("未找到处理结果文件"))
            except Exception as e:
                logger.error(f"生成综述失败: {e}")
                self.root.after(0, lambda: self.process_failed(str(e)))
        
        import threading
        thread = threading.Thread(target=generate_thread)
        thread.daemon = True
        thread.start()
    
    def generation_complete(self, result_file):
        """生成综述完成"""
        self.status_var.set("生成完成")
        self.process_button.config(state=tk.NORMAL)
        self.generate_review_button.config(state=tk.NORMAL)
        messagebox.showinfo("成功", f"综述生成完成！\n结果已保存到: {result_file}")


def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 如果提供了文件路径，从文件中读取大纲
        outline_file = sys.argv[1]
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_text = f.read()
                
                processor = OutlineProcessor()
                result_file = processor.process_outline(outline_text)
                print(f"处理完成，结果已保存到: {result_file}")
            except Exception as e:
                print(f"处理失败: {e}")
        else:
            print(f"文件不存在: {outline_file}")
    else:
        # 否则启动GUI界面
        root = tk.Tk()
        app = OutlineProcessorApp(root)
        root.mainloop()


if __name__ == "__main__":
    main() 