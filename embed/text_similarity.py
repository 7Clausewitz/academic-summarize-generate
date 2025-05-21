#!/usr/bin/env python3
"""
文本相似度检索工具：基于嵌入向量计算文本相似度并进行检索
"""

import os
import json
import numpy as np
import sys
from typing import List, Dict, Tuple, Optional, Union
import time

# 确保embed包可以被导入
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


def load_embeddings(embeddings_file: str) -> List[Dict]:
    """
    加载嵌入向量数据
    
    Args:
        embeddings_file: 嵌入向量JSON文件路径
        
    Returns:
        包含文本和嵌入向量的字典列表
    """
    if not os.path.exists(embeddings_file):
        raise FileNotFoundError(f"嵌入向量文件不存在: {embeddings_file}")
    
    with open(embeddings_file, 'r', encoding='utf-8') as f:
        embeddings_data = json.load(f)
    
    # 验证嵌入向量数据格式
    valid_count = 0
    for item in embeddings_data:
        if isinstance(item, dict) and "text" in item and "embedding" in item:
            if isinstance(item["embedding"], list) and len(item["embedding"]) > 0:
                valid_count += 1
    
    print(f"加载了 {len(embeddings_data)} 条记录，其中 {valid_count} 条有效")
    
    return embeddings_data


def normalize_vector(vector: List[float]) -> np.ndarray:
    """
    归一化向量（计算单位向量）
    
    Args:
        vector: 嵌入向量
        
    Returns:
        归一化后的单位向量
    """
    vector = np.array(vector)
    norm = np.linalg.norm(vector)
    if norm > 0:
        return vector / norm
    else:
        return vector


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec1: 第一个向量
        vec2: 第二个向量
        
    Returns:
        余弦相似度（范围 -1 到 1，值越大表示越相似）
    """
    # 安全检查：确保向量非空
    if len(vec1) == 0 or len(vec2) == 0:
        return 0.0
    
    # 已归一化的向量，直接计算点积即可得到余弦相似度
    return np.dot(vec1, vec2)


def search_similar_text(
    query_vector: Union[List[float], np.ndarray],
    embeddings_data: List[Dict],
    top_k: int = 10,
    threshold: float = 0.5
) -> List[Dict]:
    """
    搜索与查询向量最相似的文本
    
    Args:
        query_vector: 查询文本的嵌入向量
        embeddings_data: 嵌入向量数据集
        top_k: 返回的最相似文本数量
        threshold: 相似度阈值（低于此值的结果将被过滤）
        
    Returns:
        包含相似文本及其相似度的字典列表，按相似度降序排列
    """
    # 将输入向量转换为NumPy数组并归一化
    query_vector = normalize_vector(query_vector)
    
    # 计算相似度
    similarities = []
    start_time = time.time()
    
    for i, item in enumerate(embeddings_data):
        if "embedding" not in item or not item["embedding"]:
            continue
        
        # 获取嵌入向量
        embedding = item["embedding"]
        
        # 检查嵌入向量的类型
        if isinstance(embedding, dict) and "vector" in embedding:
            embedding = embedding["vector"]
        elif isinstance(embedding, dict) and "embedding" in embedding:
            embedding = embedding["embedding"]
        
        # 确保嵌入向量是列表类型
        if not isinstance(embedding, list):
            continue
        
        # 归一化嵌入向量
        normalized_embedding = normalize_vector(embedding)
        
        # 计算余弦相似度
        similarity = cosine_similarity(query_vector, normalized_embedding)
        
        # 如果相似度高于阈值，添加到结果列表
        if similarity > threshold:
            similarities.append({
                "index": i,
                "text": item.get("text", ""),
                "similarity": similarity,
                "metadata": item.get("metadata", {})
            })
    
    # 按相似度降序排序
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    # 返回前top_k个结果
    elapsed_time = time.time() - start_time
    print(f"搜索耗时: {elapsed_time:.3f}秒，找到 {len(similarities)} 个相似结果")
    
    return similarities[:top_k]


def create_query_embedding(
    query_text: str,
    api_client=None,
    model: str = "doubao-embedding-text-240715"
) -> Optional[List[float]]:
    """
    为查询文本创建嵌入向量
    
    Args:
        query_text: 查询文本
        api_client: API客户端实例
        model: 嵌入模型名称
        
    Returns:
        查询文本的嵌入向量，如果生成失败则返回None
    """
    if not api_client:
        print("错误: 未提供API客户端")
        return None
    
    try:
        print(f"为查询文本生成嵌入向量...")
        
        # 调用嵌入API
        response = api_client.embeddings.create(
            model=model,
            input=[query_text],
            encoding_format="float",
        )
        
        # 解析响应
        if hasattr(response, 'data') and response.data:
            embedding_data = response.data[0]
            
            # 提取嵌入向量
            if hasattr(embedding_data, 'embedding'):
                return embedding_data.embedding
            elif hasattr(embedding_data, '__dict__'):
                data_dict = embedding_data.__dict__
                if 'embedding' in data_dict:
                    return data_dict['embedding']
            
            # 处理其他可能的响应格式
            if isinstance(embedding_data, dict):
                if 'embedding' in embedding_data:
                    return embedding_data['embedding']
                elif 'vector' in embedding_data:
                    return embedding_data['vector']
            
            print(f"警告: 无法从响应中提取嵌入向量")
            print(f"响应类型: {type(embedding_data)}")
            print(f"响应属性: {dir(embedding_data)}")
            return None
        else:
            print(f"错误: API返回格式异常，缺少数据字段")
            print(f"响应内容: {response}")
            return None
    
    except Exception as e:
        print(f"创建嵌入向量时出错: {str(e)}")
        return None


def search_by_text(
    query_text: str,
    embeddings_file: str,
    api_client=None,
    model: str = "doubao-embedding-text-240715",
    top_k: int = 10,
    threshold: float = 0.5
) -> List[Dict]:
    """
    根据查询文本搜索相似文本
    
    Args:
        query_text: 查询文本
        embeddings_file: 嵌入向量文件路径
        api_client: API客户端实例
        model: 嵌入模型名称
        top_k: 返回的最相似文本数量
        threshold: 相似度阈值
        
    Returns:
        相似文本列表
    """
    if not api_client:
        print("错误: 未提供API客户端")
        return []
    
    # 加载嵌入向量数据
    embeddings_data = load_embeddings(embeddings_file)
    
    # 创建查询文本的嵌入向量
    query_vector = create_query_embedding(query_text, api_client, model)
    
    if not query_vector:
        print("错误: 无法创建查询文本的嵌入向量")
        return []
    
    # 搜索相似文本
    similar_texts = search_similar_text(
        query_vector, embeddings_data, top_k, threshold
    )
    
    return similar_texts


def search_by_existing_text(
    query_text: str,
    embeddings_file: str,
    top_k: int = 10,
    threshold: float = 0.5
) -> List[Dict]:
    """
    使用现有文本的嵌入向量（如果存在于数据集中）搜索相似文本
    
    Args:
        query_text: 查询文本（应存在于数据集中）
        embeddings_file: 嵌入向量文件路径
        top_k: 返回的最相似文本数量
        threshold: 相似度阈值
        
    Returns:
        相似文本列表
    """
    # 加载嵌入向量数据
    embeddings_data = load_embeddings(embeddings_file)
    
    # 查找文本对应的嵌入向量
    query_vector = None
    query_index = -1
    
    for i, item in enumerate(embeddings_data):
        if item.get("text") == query_text:
            embedding = item.get("embedding")
            
            # 检查嵌入向量的类型
            if isinstance(embedding, dict) and "vector" in embedding:
                query_vector = embedding["vector"]
            elif isinstance(embedding, dict) and "embedding" in embedding:
                query_vector = embedding["embedding"]
            elif isinstance(embedding, list):
                query_vector = embedding
            
            query_index = i
            break
    
    if query_vector is None:
        print(f"错误: 在数据集中未找到文本 '{query_text}'")
        return []
    
    # 搜索相似文本
    similar_texts = search_similar_text(
        query_vector, embeddings_data, top_k + 1, threshold
    )
    
    # 移除查询文本本身（如果在结果中）
    filtered_results = [item for item in similar_texts if item["index"] != query_index]
    
    return filtered_results[:top_k]


def format_search_results(results: List[Dict], show_similarity: bool = True) -> str:
    """
    格式化搜索结果为友好的显示文本
    
    Args:
        results: 搜索结果列表
        show_similarity: 是否显示相似度分数
        
    Returns:
        格式化的搜索结果文本
    """
    if not results:
        return "未找到相似文本"
    
    output = f"找到 {len(results)} 个相似文本:\n\n"
    
    for i, result in enumerate(results):
        text = result["text"]
        similarity = result["similarity"]
        metadata = result.get("metadata", {})
        
        # 格式化文本预览（最多显示200个字符）
        preview = text[:200] + "..." if len(text) > 200 else text
        
        # 构建输出
        output += f"[{i+1}] "
        if show_similarity:
            output += f"相似度: {similarity:.4f} "
        
        # 添加元数据信息（如果有）
        if metadata:
            if "file_name" in metadata:
                output += f"文件: {metadata['file_name']} "
            if "title" in metadata:
                output += f"标题: {metadata['title']} "
        
        output += f"\n{preview}\n\n"
        output += "-" * 80 + "\n\n"
    
    return output


def interactive_search(embeddings_file: str, api_client=None):
    """
    交互式文本相似度搜索
    
    Args:
        embeddings_file: 嵌入向量文件路径
        api_client: API客户端实例
    """
    print("文本相似度搜索")
    print("=" * 50)
    
    while True:
        print("\n搜索选项:")
        print("1. 使用新文本搜索")
        print("2. 使用现有文本搜索")
        print("3. 退出")
        
        choice = input("\n请选择搜索方式 (1-3): ")
        
        if choice == "3":
            print("退出搜索")
            break
        
        if choice == "1":
            # 使用新文本搜索
            query_text = input("\n请输入查询文本: ")
            if not query_text:
                print("查询文本不能为空")
                continue
            
            if not api_client:
                print("错误: API客户端未初始化，无法生成新文本的嵌入向量")
                continue
            
            top_k = int(input("返回结果数量 (默认10): ") or 10)
            threshold = float(input("相似度阈值 (0-1, 默认0.5): ") or 0.5)
            
            # 搜索相似文本
            results = search_by_text(
                query_text, embeddings_file, api_client, 
                top_k=top_k, threshold=threshold
            )
            
        elif choice == "2":
            # 使用现有文本搜索
            print("\n使用数据集中已有的文本进行搜索")
            print("请提供部分文本内容，系统将尝试匹配")
            
            query_text = input("\n请输入部分文本内容: ")
            if not query_text:
                print("查询文本不能为空")
                continue
            
            # 加载嵌入数据
            embeddings_data = load_embeddings(embeddings_file)
            
            # 查找匹配文本
            matches = []
            for i, item in enumerate(embeddings_data):
                if query_text.lower() in item.get("text", "").lower():
                    preview = item["text"][:100] + "..." if len(item["text"]) > 100 else item["text"]
                    matches.append((i, preview))
                    if len(matches) >= 5:
                        break
            
            if not matches:
                print("未找到匹配的文本")
                continue
            
            # 让用户选择匹配的文本
            print("\n找到以下匹配文本:")
            for i, (idx, preview) in enumerate(matches):
                print(f"{i+1}. {preview}")
            
            choice_idx = int(input("\n请选择一个文本 (1-{0}): ".format(len(matches)))) - 1
            if choice_idx < 0 or choice_idx >= len(matches):
                print("无效的选择")
                continue
            
            # 获取完整文本
            selected_idx = matches[choice_idx][0]
            selected_text = embeddings_data[selected_idx]["text"]
            
            top_k = int(input("返回结果数量 (默认10): ") or 10)
            threshold = float(input("相似度阈值 (0-1, 默认0.5): ") or 0.5)
            
            # 搜索相似文本
            results = search_by_existing_text(
                selected_text, embeddings_file, 
                top_k=top_k, threshold=threshold
            )
            
        else:
            print("无效的选择")
            continue
        
        # 显示结果
        if results:
            formatted_results = format_search_results(results)
            print("\n搜索结果:")
            print(formatted_results)
            
            # 询问是否保存结果
            save_choice = input("是否保存结果? (y/n, 默认n): ").lower()
            if save_choice == 'y':
                save_path = input("请输入保存路径 (默认: search_results.txt): ") or "search_results.txt"
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write("查询文本: " + query_text + "\n\n")
                    f.write(formatted_results)
                print(f"结果已保存至 {save_path}")
        else:
            print("未找到相似文本")


def main():
    """
    主函数
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='文本相似度检索工具')
    parser.add_argument('--embeddings', '-e', required=True, help='嵌入向量文件路径')
    parser.add_argument('--query', '-q', help='查询文本')
    parser.add_argument('--top-k', '-k', type=int, default=10, help='返回结果数量 (默认: 10)')
    parser.add_argument('--threshold', '-t', type=float, default=0.5, help='相似度阈值 (默认: 0.5)')
    parser.add_argument('--interactive', '-i', action='store_true', help='启用交互式搜索')
    
    args = parser.parse_args()
    
    # 检查是否有API客户端
    api_client = None
    try:
        from volcenginesdkarkruntime import Ark
        from text_processor import API_KEY
        api_client = Ark(api_key=API_KEY)
        print("已初始化API客户端")
    except (ImportError, ModuleNotFoundError):
        print("警告: 未找到volcenginesdkarkruntime模块或API密钥，将无法使用新文本搜索功能")
    
    # 交互式模式
    if args.interactive:
        interactive_search(args.embeddings, api_client)
        return
    
    # 命令行模式
    if not args.query:
        print("错误: 必须提供查询文本或使用交互式模式")
        return
    
    # 使用新文本搜索
    if api_client:
        results = search_by_text(
            args.query, args.embeddings, api_client, 
            top_k=args.top_k, threshold=args.threshold
        )
    else:
        # 尝试使用现有文本
        results = search_by_existing_text(
            args.query, args.embeddings, 
            top_k=args.top_k, threshold=args.threshold
        )
    
    # 显示结果
    if results:
        formatted_results = format_search_results(results)
        print("\n搜索结果:")
        print(formatted_results)
    else:
        print("未找到相似文本")


if __name__ == "__main__":
    main() 