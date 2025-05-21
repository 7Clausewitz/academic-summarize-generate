#!/usr/bin/env python3
"""
文本处理集成模块：整合XML文本提取和相似度检索功能
"""

import os
import json
import argparse
import sys
from typing import List, Dict, Optional
import re

# 确保embed包可以被导入
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 导入子模块（使用绝对导入）
try:
    from embed.xml_text_extractor import extract_paragraphs_with_metadata, process_directory_with_metadata
    from embed.text_similarity import load_embeddings, create_query_embedding, search_similar_text, format_search_results
except ImportError:
    # 当作为模块导入时尝试相对导入
    try:
        from .xml_text_extractor import extract_paragraphs_with_metadata, process_directory_with_metadata
        from .text_similarity import load_embeddings, create_query_embedding, search_similar_text, format_search_results
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保在正确的目录中运行此脚本，或将embed目录添加到Python路径")
        sys.exit(1)

# 从.env文件加载环境变量
def load_env_file():
    """从.env文件加载环境变量"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        print(f"正在从 {env_path} 加载环境变量...")
        with open(env_path, 'r', encoding='utf-8') as env_file:
            for line in env_file:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue
                # 提取键值对
                match = re.match(r'^([A-Za-z0-9_]+)=(.*)$', line)
                if match:
                    key, value = match.groups()
                    # 清除值中的注释
                    value = value.split('#')[0].strip()
                    os.environ[key] = value
                    print(f"  设置环境变量: {key}=***")
        return True
    else:
        print(f"未找到.env文件: {env_path}")
        return False

# 加载.env文件
load_env_file()

# API密钥配置（优先从环境变量获取，然后尝试从.env文件获取）
API_KEY = os.environ.get("DOUBAO_API_KEY", "") or os.environ.get("ARK_API_KEY", "")

def extract_and_create_embeddings(
    input_path: str,
    output_file: str,
    api_client=None,
    model: str = None,
    file_pattern: str = "*.xml",
    batch_size: int = None
) -> bool:
    """
    从XML文件中提取文本并生成嵌入向量
    
    Args:
        input_path: 输入文件或目录路径
        output_file: 输出嵌入向量文件路径
        api_client: API客户端实例
        model: 嵌入模型名称
        file_pattern: 匹配XML文件的模式
        batch_size: 批量处理大小
        
    Returns:
        处理是否成功
    """
    if not api_client:
        print("错误: 未提供API客户端，无法生成嵌入向量")
        return False
    
    # 获取配置参数，优先使用函数参数，其次是环境变量，最后是默认值
    model = model or os.environ.get("EMBEDDING_MODEL", "doubao-embedding-text-240715")
    
    try:
        batch_size = batch_size or int(os.environ.get("BATCH_SIZE", "10"))
    except (ValueError, TypeError):
        batch_size = 10
        print(f"警告: BATCH_SIZE环境变量无效，使用默认值 {batch_size}")
    
    print(f"使用模型: {model}")
    print(f"批处理大小: {batch_size}")
    
    # 提取文本
    print(f"从 {input_path} 提取文本...")
    paragraphs = []
    
    if os.path.isdir(input_path):
        paragraphs = process_directory_with_metadata(input_path, file_pattern)
    elif os.path.isfile(input_path):
        paragraphs = extract_paragraphs_with_metadata(input_path)
    else:
        print(f"错误: 路径不存在 {input_path}")
        return False
    
    if not paragraphs:
        print("未找到文本段落")
        return False
    
    print(f"共提取了 {len(paragraphs)} 个文本段落")
    
    # 生成嵌入向量
    print("正在生成嵌入向量...")
    embeddings_data = []
    
    for i in range(0, len(paragraphs), batch_size):
        batch = paragraphs[i:i+batch_size]
        print(f"处理批次 {i//batch_size + 1}/{(len(paragraphs)-1)//batch_size + 1}...")
        
        for item in batch:
            text = item["content"]
            
            # 生成嵌入向量
            try:
                embedding = create_query_embedding(text, api_client, model)
                
                if embedding:
                    embeddings_data.append({
                        "text": text,
                        "embedding": embedding,
                        "metadata": item.get("metadata", {})
                    })
                else:
                    print(f"警告: 无法为文本生成嵌入向量: {text[:50]}...")
            except Exception as e:
                print(f"处理文本时出错: {str(e)}")
    
    # 保存嵌入向量数据
    if embeddings_data:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, ensure_ascii=False, indent=2)
        
        print(f"已将 {len(embeddings_data)} 条嵌入向量数据保存至 {output_file}")
        return True
    else:
        print("错误: 未生成任何嵌入向量")
        return False


def process_and_search(
    input_path: str,
    query_text: str,
    embeddings_file: str = None,
    api_client=None,
    top_k: int = 10,
    threshold: float = 0.5,
    save_embeddings: bool = True
) -> List[Dict]:
    """
    一站式处理：提取文本、生成嵌入向量并搜索相似文本
    
    Args:
        input_path: 输入XML文件或目录路径
        query_text: 查询文本
        embeddings_file: 嵌入向量文件路径（如果不提供将创建临时文件）
        api_client: API客户端实例
        top_k: 返回结果数量
        threshold: 相似度阈值
        save_embeddings: 是否保存生成的嵌入向量
        
    Returns:
        相似文本搜索结果
    """
    if not api_client:
        print("错误: 未提供API客户端，无法执行搜索")
        return []
    
    # 创建临时嵌入向量文件
    temp_embeddings_file = embeddings_file or "temp_embeddings.json"
    
    # 提取文本并生成嵌入向量
    success = extract_and_create_embeddings(
        input_path, temp_embeddings_file, api_client
    )
    
    if not success:
        print("错误: 无法完成文本提取和嵌入向量生成")
        return []
    
    # 为查询文本创建嵌入向量
    query_vector = create_query_embedding(query_text, api_client)
    
    if not query_vector:
        print("错误: 无法为查询文本创建嵌入向量")
        return []
    
    # 加载嵌入向量数据
    embeddings_data = load_embeddings(temp_embeddings_file)
    
    # 搜索相似文本
    search_results = search_similar_text(
        query_vector, embeddings_data, top_k, threshold
    )
    
    # 如果不需要保存嵌入向量文件且使用的是临时文件，则删除它
    if not save_embeddings and not embeddings_file:
        try:
            os.remove(temp_embeddings_file)
            print(f"已删除临时嵌入向量文件 {temp_embeddings_file}")
        except Exception as e:
            print(f"警告: 无法删除临时文件: {str(e)}")
    
    return search_results


def initialize_api_client():
    """
    初始化API客户端
    
    Returns:
        API客户端实例，如果初始化失败则返回None
    """
    try:
        from volcenginesdkarkruntime import Ark
        
        if not API_KEY:
            print("警告: 未设置API密钥，请设置环境变量DOUBAO_API_KEY或ARK_API_KEY")
            return None
        
        # 打印API信息
        print(f"使用API密钥初始化客户端: {API_KEY[:4]}...{API_KEY[-4:]}")
        
        # 尝试获取自定义API基础URL（如果有）
        base_url = os.environ.get("ARK_BASE_URL", None)
        if base_url:
            print(f"使用自定义API基础URL: {base_url}")
            api_client = Ark(api_key=API_KEY, base_url=base_url)
        else:
            api_client = Ark(api_key=API_KEY)
        
        print("API客户端初始化成功")
        return api_client
    except ImportError:
        print("错误: 未安装volcenginesdkarkruntime模块")
        print("请使用以下命令安装: pip install volcenginesdkarkruntime")
        return None
    except Exception as e:
        print(f"API客户端初始化失败: {str(e)}")
        return None


def interactive():
    """
    交互式文本处理界面
    """
    print("文本处理工具")
    print("=" * 50)
    
    # 初始化API客户端
    api_client = initialize_api_client()
    if not api_client:
        print("警告: API客户端初始化失败，部分功能将不可用")
    
    while True:
        print("\n请选择操作:")
        print("1. 从XML文件提取文本并生成嵌入向量")
        print("2. 使用嵌入向量搜索相似文本")
        print("3. 一站式处理（提取、生成、搜索）")
        print("4. 退出")
        
        choice = input("\n请选择 (1-4): ")
        
        if choice == "1":
            # 从XML文件提取文本并生成嵌入向量
            input_path = input("请输入XML文件或目录路径: ")
            if not input_path:
                print("路径不能为空")
                continue
            
            if not os.path.exists(input_path):
                print(f"路径不存在: {input_path}")
                continue
            
            if not api_client:
                print("错误: API客户端未初始化，无法生成嵌入向量")
                continue
            
            output_file = input("请输入输出文件路径 (默认: embeddings.json): ") or "embeddings.json"
            file_pattern = input("请输入文件匹配模式 (默认: *.xml): ") or "*.xml"
            
            success = extract_and_create_embeddings(
                input_path, output_file, api_client, file_pattern=file_pattern
            )
            
            if success:
                print(f"处理完成，结果保存至 {output_file}")
        
        elif choice == "2":
            # 使用嵌入向量搜索相似文本
            embeddings_file = input("请输入嵌入向量文件路径: ")
            if not embeddings_file:
                print("文件路径不能为空")
                continue
            
            if not os.path.exists(embeddings_file):
                print(f"文件不存在: {embeddings_file}")
                continue
            
            query_text = input("请输入查询文本: ")
            if not query_text:
                print("查询文本不能为空")
                continue
            
            if not api_client:
                print("错误: API客户端未初始化，无法生成查询嵌入向量")
                continue
            
            top_k = int(input("返回结果数量 (默认10): ") or 10)
            threshold = float(input("相似度阈值 (0-1, 默认0.5): ") or 0.5)
            
            # 为查询文本创建嵌入向量
            query_vector = create_query_embedding(query_text, api_client)
            
            if not query_vector:
                print("错误: 无法为查询文本创建嵌入向量")
                continue
            
            # 加载嵌入向量数据
            embeddings_data = load_embeddings(embeddings_file)
            
            # 搜索相似文本
            search_results = search_similar_text(
                query_vector, embeddings_data, top_k, threshold
            )
            
            # 显示结果
            if search_results:
                formatted_results = format_search_results(search_results)
                print("\n搜索结果:")
                print(formatted_results)
                
                save_choice = input("是否保存结果? (y/n, 默认n): ").lower()
                if save_choice == 'y':
                    save_path = input("请输入保存路径 (默认: search_results.txt): ") or "search_results.txt"
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write("查询文本: " + query_text + "\n\n")
                        f.write(formatted_results)
                    print(f"结果已保存至 {save_path}")
            else:
                print("未找到相似文本")
        
        elif choice == "3":
            # 一站式处理
            input_path = input("请输入XML文件或目录路径: ")
            if not input_path:
                print("路径不能为空")
                continue
            
            if not os.path.exists(input_path):
                print(f"路径不存在: {input_path}")
                continue
            
            query_text = input("请输入查询文本: ")
            if not query_text:
                print("查询文本不能为空")
                continue
            
            if not api_client:
                print("错误: API客户端未初始化，无法执行搜索")
                continue
            
            save_embeddings = input("是否保存嵌入向量? (y/n, 默认y): ").lower() != 'n'
            embeddings_file = None
            if save_embeddings:
                embeddings_file = input("请输入嵌入向量文件路径 (默认: embeddings.json): ") or "embeddings.json"
            
            top_k = int(input("返回结果数量 (默认10): ") or 10)
            threshold = float(input("相似度阈值 (0-1, 默认0.5): ") or 0.5)
            
            # 执行一站式处理
            search_results = process_and_search(
                input_path, query_text, embeddings_file,
                api_client, top_k, threshold, save_embeddings
            )
            
            # 显示结果
            if search_results:
                formatted_results = format_search_results(search_results)
                print("\n搜索结果:")
                print(formatted_results)
                
                save_choice = input("是否保存结果? (y/n, 默认n): ").lower()
                if save_choice == 'y':
                    save_path = input("请输入保存路径 (默认: search_results.txt): ") or "search_results.txt"
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write("查询文本: " + query_text + "\n\n")
                        f.write(formatted_results)
                    print(f"结果已保存至 {save_path}")
            else:
                print("未找到相似文本")
        
        elif choice == "4":
            print("退出程序")
            break
        
        else:
            print("无效的选择")


def main():
    """
    命令行界面
    """
    parser = argparse.ArgumentParser(description='文本处理工具')
    
    # 创建子命令
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # 提取文本并生成嵌入向量的子命令
    extract_parser = subparsers.add_parser('extract', help='从XML文件提取文本并生成嵌入向量')
    extract_parser.add_argument('--input', '-i', required=True, help='输入XML文件或目录路径')
    extract_parser.add_argument('--output', '-o', default='embeddings.json', help='输出嵌入向量文件路径')
    extract_parser.add_argument('--pattern', '-p', default='*.xml', help='匹配XML文件的模式')
    
    # 搜索相似文本的子命令
    search_parser = subparsers.add_parser('search', help='搜索相似文本')
    search_parser.add_argument('--embeddings', '-e', required=True, help='嵌入向量文件路径')
    search_parser.add_argument('--query', '-q', required=True, help='查询文本')
    search_parser.add_argument('--top-k', '-k', type=int, default=10, help='返回结果数量')
    search_parser.add_argument('--threshold', '-t', type=float, default=0.5, help='相似度阈值')
    
    # 一站式处理的子命令
    process_parser = subparsers.add_parser('process', help='一站式处理（提取、生成、搜索）')
    process_parser.add_argument('--input', '-i', required=True, help='输入XML文件或目录路径')
    process_parser.add_argument('--query', '-q', required=True, help='查询文本')
    process_parser.add_argument('--embeddings', '-e', help='嵌入向量文件路径')
    process_parser.add_argument('--top-k', '-k', type=int, default=10, help='返回结果数量')
    process_parser.add_argument('--threshold', '-t', type=float, default=0.5, help='相似度阈值')
    process_parser.add_argument('--no-save', '-n', action='store_true', help='不保存嵌入向量')
    
    # 交互式模式
    parser.add_argument('--interactive', '-i', action='store_true', help='启用交互式模式')
    
    args = parser.parse_args()
    
    # 初始化API客户端
    api_client = initialize_api_client()
    if not api_client:
        print("警告: API客户端初始化失败，部分功能将不可用")
    
    # 交互式模式
    if args.interactive:
        interactive()
        return
    
    # 执行对应的命令
    if args.command == 'extract':
        if not api_client:
            print("错误: API客户端未初始化，无法生成嵌入向量")
            return
        
        extract_and_create_embeddings(
            args.input, args.output, api_client, file_pattern=args.pattern
        )
    
    elif args.command == 'search':
        if not api_client:
            print("错误: API客户端未初始化，无法生成查询嵌入向量")
            return
        
        # 为查询文本创建嵌入向量
        query_vector = create_query_embedding(args.query, api_client)
        
        if not query_vector:
            print("错误: 无法为查询文本创建嵌入向量")
            return
        
        # 加载嵌入向量数据
        embeddings_data = load_embeddings(args.embeddings)
        
        # 搜索相似文本
        search_results = search_similar_text(
            query_vector, embeddings_data, args.top_k, args.threshold
        )
        
        # 显示结果
        if search_results:
            formatted_results = format_search_results(search_results)
            print("\n搜索结果:")
            print(formatted_results)
        else:
            print("未找到相似文本")
    
    elif args.command == 'process':
        if not api_client:
            print("错误: API客户端未初始化，无法执行搜索")
            return
        
        # 执行一站式处理
        search_results = process_and_search(
            args.input, args.query, args.embeddings,
            api_client, args.top_k, args.threshold, not args.no_save
        )
        
        # 显示结果
        if search_results:
            formatted_results = format_search_results(search_results)
            print("\n搜索结果:")
            print(formatted_results)
        else:
            print("未找到相似文本")
    
    else:
        # 如果没有指定命令，显示帮助信息
        parser.print_help()


if __name__ == "__main__":
    main() 