#!/usr/bin/env python3
"""
摘要和标题提取器：从XML文件中提取标题和摘要信息并构建嵌入检索
"""

import os
import re
import glob
import json
import argparse
import sys
import time
from typing import List, Dict, Tuple, Optional, Union
import numpy as np

# 确保embed包可以被导入
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 尝试导入相关模块
try:
    from embed.text_similarity import (
        load_embeddings, normalize_vector, cosine_similarity, 
        create_query_embedding, search_similar_text, format_search_results
    )
except ImportError:
    # 当作为模块导入时尝试相对导入
    try:
        from .text_similarity import (
            load_embeddings, normalize_vector, cosine_similarity, 
            create_query_embedding, search_similar_text, format_search_results
        )
    except ImportError as e:
        print(f"导入错误: {e}")
        print("请确保在正确的目录中运行此脚本，或将embed目录添加到Python路径")
        sys.exit(1)


def extract_title_from_file(file_path: str) -> str:
    """
    从XML文件中提取标题
    
    Args:
        file_path: XML文件路径
        
    Returns:
        标题文本
    """
    try:
        # 以纯文本形式读取文件
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 使用正则表达式查找<title level="a" type="main">标签中的内容
        title_pattern = re.compile(r'<title\s+level="a"\s+type="main">(.*?)</title>', re.DOTALL)
        title_match = title_pattern.search(content)
        
        if title_match:
            title = title_match.group(1).strip()
            print(f"从文件 {file_path} 中提取了标题: {title[:50]}...")
            return title
        else:
            print(f"在文件 {file_path} 中未找到标题")
            return ""
            
    except Exception as e:
        print(f"提取标题时出错 {file_path}: {e}")
        return ""


def extract_abstract_from_file(file_path: str) -> str:
    """
    从XML文件中提取摘要，去除type='figure'的内容
    
    Args:
        file_path: XML文件路径
        
    Returns:
        摘要文本
    """
    try:
        # 以纯文本形式读取文件
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 使用正则表达式查找<abstract>标签中的内容
        abstract_pattern = re.compile(r'<abstract>(.*?)</abstract>', re.DOTALL)
        abstract_match = abstract_pattern.search(content)
        
        if abstract_match:
            # 获取原始摘要文本
            abstract = abstract_match.group(1).strip()
            
            # 移除图表引用 (type="figure" 的 ref 标签)
            figure_ref_pattern = re.compile(r'<ref\s+type="figure".*?>.*?</ref>', re.DOTALL)
            abstract = figure_ref_pattern.sub('', abstract)
            
            # 打印调试信息
            print(f"从文件 {file_path} 中提取了摘要: {abstract[:50]}...")
            
            return abstract
        else:
            print(f"在文件 {file_path} 中未找到摘要")
            return ""
            
    except Exception as e:
        print(f"提取摘要时出错 {file_path}: {e}")
        return ""


def extract_info_from_file(file_path: str) -> Dict:
    """
    从XML文件中提取标题和摘要，并合并为文章简略信息
    
    Args:
        file_path: XML文件路径
        
    Returns:
        包含标题、摘要和合并信息的字典
    """
    try:
        title = extract_title_from_file(file_path)
        abstract = extract_abstract_from_file(file_path)
        
        # 从文件名中提取元数据
        file_name = os.path.basename(file_path)
        metadata = {}
        if " - " in file_name:
            parts = file_name.split(" - ")
            if len(parts) >= 3:
                metadata["journal"] = parts[0].strip()
                metadata["year"] = parts[1].strip()
                metadata["author"] = parts[2].split(" ")[0].strip()
        
        # 合并标题和摘要
        combined_info = ""
        if title:
            combined_info += f"标题: {title}\n"
        if abstract:
            combined_info += f"摘要: {abstract}"
        
        return {
            "title": title,
            "abstract": abstract,
            "combined_info": combined_info.strip(),
            "file_path": file_path,
            "file_name": file_name,
            "metadata": metadata
        }
        
    except Exception as e:
        print(f"提取文件信息时出错 {file_path}: {e}")
        return {
            "title": "",
            "abstract": "",
            "combined_info": "",
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "metadata": {}
        }


def process_directory(directory: str, file_pattern: str = "*.xml") -> List[Dict]:
    """
    处理目录中的所有XML文件
    
    Args:
        directory: 包含XML文件的目录
        file_pattern: 匹配XML文件的glob模式
        
    Returns:
        包含文件信息的字典列表
    """
    if not directory:
        raise ValueError("未指定目录")
    
    result = []
    file_paths = glob.glob(os.path.join(directory, file_pattern))
    print(f"在目录 {directory} 中找到 {len(file_paths)} 个匹配文件")
    
    for file_path in file_paths:
        file_info = extract_info_from_file(file_path)
        if file_info["combined_info"]:  # 只添加有内容的文件信息
            result.append(file_info)
        
    return result


def save_info_to_file(info_list: List[Dict], output_file: str):
    """
    将提取的信息保存到JSON文件
    
    Args:
        info_list: 包含文件信息的字典列表
        output_file: 保存输出的文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(info_list, f, ensure_ascii=False, indent=2)
    
    print(f"保存了 {len(info_list)} 条文件记录到 {output_file}")


def create_embeddings_from_info(
    info_list: List[Dict],
    output_file: str,
    api_client=None,
    model: str = "doubao-embedding-text-240715",
    batch_size: int = 10
) -> bool:
    """
    为文章简略信息创建嵌入向量
    
    Args:
        info_list: 包含文件信息的字典列表
        output_file: 输出嵌入向量文件路径
        api_client: API客户端实例
        model: 嵌入模型名称
        batch_size: 批量处理大小
        
    Returns:
        处理是否成功
    """
    if not api_client:
        print("错误: 未提供API客户端，无法生成嵌入向量")
        return False
    
    if not info_list:
        print("错误: 没有可处理的文件信息")
        return False
    
    print(f"为 {len(info_list)} 条文件信息生成嵌入向量...")
    embeddings_data = []
    errors_count = 0
    
    for i in range(0, len(info_list), batch_size):
        batch = info_list[i:i+batch_size]
        print(f"处理批次 {i//batch_size + 1}/{(len(info_list)-1)//batch_size + 1}...")
        
        for item in batch:
            try:
                text = item["combined_info"]
                file_name = item.get("file_name", "未知文件")
                print(f"处理文档: {file_name[:50]}...")
                
                # 生成嵌入向量
                embedding = create_query_embedding(text, api_client, model)
                
                if embedding:
                    embeddings_data.append({
                        "text": text,
                        "embedding": embedding,
                        "title": item.get("title", ""),
                        "abstract": item.get("abstract", ""),
                        "file_path": item.get("file_path", ""),
                        "file_name": file_name,
                        "metadata": item.get("metadata", {})
                    })
                    print(f"✓ 成功创建嵌入向量 - {file_name[:50]}")
                else:
                    print(f"✗ 警告: 无法为文档生成嵌入向量: {file_name}")
                    errors_count += 1
            except Exception as e:
                print(f"✗ 处理文档时出错 ({item.get('file_name', '未知')}): {str(e)}")
                errors_count += 1
                # 继续处理下一篇文档
                continue
    
    # 保存嵌入向量数据
    if embeddings_data:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, ensure_ascii=False, indent=2)
        
        if errors_count > 0:
            print(f"已将 {len(embeddings_data)}/{len(info_list)} 条嵌入向量数据保存至 {output_file}")
            print(f"警告: {errors_count} 条记录处理失败")
        else:
            print(f"已将全部 {len(embeddings_data)} 条嵌入向量数据保存至 {output_file}")
        return True
    else:
        print("错误: 未生成任何嵌入向量")
        return False


def search_by_text(
    query_text: str,
    embeddings_file: str,
    api_client=None,
    model: str = "doubao-embedding-text-240715",
    top_k: int = 10,
    threshold: float = 0.5
) -> List[Dict]:
    """
    根据查询文本搜索相似文章
    
    Args:
        query_text: 查询文本
        embeddings_file: 嵌入向量文件路径
        api_client: API客户端实例
        model: 嵌入模型名称
        top_k: 返回的最相似文章数量
        threshold: 相似度阈值
        
    Returns:
        相似文章列表
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
    
    # 搜索相似文章
    similar_texts = search_similar_text(
        query_vector, embeddings_data, top_k, threshold
    )
    
    return similar_texts


def process_and_search(
    input_path: str,
    query_text: str,
    embeddings_file: str = None,
    api_client=None,
    top_k: int = 10,
    threshold: float = 0.5,
    save_embeddings: bool = True,
    file_pattern: str = "*.xml"
) -> List[Dict]:
    """
    一站式处理：提取文章信息、生成嵌入向量并搜索相似文章
    
    Args:
        input_path: 输入XML文件或目录路径
        query_text: 查询文本
        embeddings_file: 嵌入向量文件路径（如果不提供将创建临时文件）
        api_client: API客户端实例
        top_k: 返回结果数量
        threshold: 相似度阈值
        save_embeddings: 是否保存生成的嵌入向量
        file_pattern: 匹配XML文件的glob模式
        
    Returns:
        相似文章搜索结果
    """
    if not api_client:
        print("错误: 未提供API客户端，无法执行搜索")
        return []
    
    # 创建临时嵌入向量文件
    temp_embeddings_file = embeddings_file or "temp_article_embeddings.json"
    
    # 提取文章信息
    info_list = []
    if os.path.isdir(input_path):
        info_list = process_directory(input_path, file_pattern)
    elif os.path.isfile(input_path):
        file_info = extract_info_from_file(input_path)
        if file_info["combined_info"]:
            info_list = [file_info]
    else:
        print(f"错误: 路径不存在 {input_path}")
        return []
    
    if not info_list:
        print("未找到文章信息")
        return []
    
    # 生成嵌入向量
    success = create_embeddings_from_info(
        info_list, temp_embeddings_file, api_client
    )
    
    if not success:
        print("错误: 无法完成文章信息的嵌入向量生成")
        return []
    
    # 搜索相似文章
    search_results = search_by_text(
        query_text, temp_embeddings_file, api_client, 
        top_k=top_k, threshold=threshold
    )
    
    # 如果不需要保存嵌入向量文件且使用的是临时文件，则删除它
    if not save_embeddings and not embeddings_file:
        try:
            os.remove(temp_embeddings_file)
            print(f"已删除临时嵌入向量文件 {temp_embeddings_file}")
        except Exception as e:
            print(f"警告: 无法删除临时文件: {str(e)}")
    
    return search_results


def format_article_results(results: List[Dict], show_similarity: bool = True) -> str:
    """
    格式化文章搜索结果为易读的字符串
    
    Args:
        results: 搜索结果列表
        show_similarity: 是否显示相似度分数
        
    Returns:
        格式化的结果字符串
    """
    if not results:
        return "未找到匹配结果"
    
    formatted_text = f"找到 {len(results)} 个相似文章:\n\n"
    
    for i, result in enumerate(results):
        formatted_text += f"--- 结果 {i+1} "
        if show_similarity:
            similarity = result.get("similarity", 0)
            formatted_text += f"(相似度: {similarity:.2f}) "
        formatted_text += "---\n"
        
        # 添加文件名
        file_name = result.get("file_name", "")
        if file_name:
            formatted_text += f"文件: {file_name}\n"
        
        # 添加标题
        title = result.get("title", "")
        if title:
            formatted_text += f"标题: {title}\n"
        
        # 添加摘要摘录
        abstract = result.get("abstract", "")
        if abstract:
            # 显示摘要的前200个字符
            preview = abstract[:200] + ("..." if len(abstract) > 200 else "")
            formatted_text += f"摘要: {preview}\n"
        
        # 添加元数据
        metadata = result.get("metadata", {})
        if metadata:
            meta_str = ", ".join([f"{k}: {v}" for k, v in metadata.items()])
            formatted_text += f"元数据: {meta_str}\n"
        
        formatted_text += "\n"
    
    return formatted_text


def interactive_search(embeddings_file: str, api_client=None):
    """
    交互式搜索界面
    
    Args:
        embeddings_file: 嵌入向量文件路径
        api_client: API客户端实例
    """
    if not api_client:
        print("错误: 未提供API客户端，无法执行搜索")
        return
    
    print(f"\n=== 文章相似度搜索 ===")
    print(f"使用嵌入向量文件: {embeddings_file}")
    
    while True:
        query = input("\n请输入搜索查询 (输入 'exit' 退出): ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("退出搜索")
            break
        
        if not query:
            print("查询不能为空")
            continue
        
        # 设置搜索参数
        top_k = 5
        threshold = 0.5
        
        # 执行搜索
        results = search_by_text(
            query, embeddings_file, api_client, top_k=top_k, threshold=threshold
        )
        
        # 显示结果
        print("\n搜索结果:")
        formatted_results = format_article_results(results)
        print(formatted_results)


def main():
    """
    命令行界面
    """
    parser = argparse.ArgumentParser(
        description='从XML文件中提取标题和摘要，并进行嵌入和检索'
    )
    
    # 添加GUI参数首先检查
    parser.add_argument(
        '--gui', '-g',
        action='store_true',
        help='启动图形用户界面'
    )
    
    # 如果只有-g或--gui参数，则直接启动GUI
    if len(sys.argv) == 2 and (sys.argv[1] == '-g' or sys.argv[1] == '--gui'):
        launch_gui()
        return
    
    # 检查是否只是进行查询模式
    query_mode = False
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg in ['-q', '--query'] and i < len(sys.argv)-1:
                query_mode = True
            if arg in ['-e', '--embeddings'] and i < len(sys.argv)-1:
                query_mode = True
    
    parser.add_argument(
        '--input', '-i', 
        required=not query_mode,  # 如果是查询模式，则不要求输入
        help='输入XML文件或包含XML文件的目录'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='保存提取信息的输出文件（默认：article_info.json）'
    )
    
    parser.add_argument(
        '--embeddings', '-e',
        help='嵌入向量输出/输入文件（默认：article_embeddings.json）'
    )
    
    parser.add_argument(
        '--pattern', '-p',
        default='*.xml',
        help='匹配XML文件的模式（默认：*.xml）'
    )
    
    parser.add_argument(
        '--query', '-q',
        help='查询文本，如果提供则执行搜索'
    )
    
    parser.add_argument(
        '--interactive', '-I',
        action='store_true',
        help='启动交互式搜索界面'
    )
    
    parser.add_argument(
        '--top-k', '-k',
        type=int,
        default=5,
        help='返回的最相似结果数量（默认：5）'
    )
    
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=0.5,
        help='相似度阈值（默认：0.5）'
    )
    
    # 解析参数
    try:
        args = parser.parse_args()
    except SystemExit:
        # 如果参数解析失败，向用户提供更友好的提示
        if query_mode:
            print("\n提示: 要进行查询，请确保同时提供 --query/-q 和 --embeddings/-e 参数\n例如:")
            print("  python abstract_extractor.py -e article_embeddings.json -q \"纳米材料\" -k 3\n")
        sys.exit(1)
    
    # 启动GUI
    if args.gui:
        launch_gui()
        return
    
    # 导入和初始化API客户端
    try:
        from embed.text_processor import initialize_api_client
        api_client = initialize_api_client()
        
        if not api_client:
            print("错误: 无法初始化API客户端，请检查API密钥配置")
            sys.exit(1)
    except ImportError:
        print("错误: 无法导入initialize_api_client")
        sys.exit(1)
    
    # 设置嵌入向量文件路径
    embeddings_output_file = args.embeddings or "article_embeddings.json"
    
    # 如果是查询模式，则直接执行查询
    if (args.query or args.interactive) and not args.input:
        if not os.path.exists(embeddings_output_file):
            print(f"错误: 嵌入向量文件不存在: {embeddings_output_file}")
            print("请先提取文章信息并生成嵌入向量，或者指定正确的嵌入向量文件路径")
            sys.exit(1)
            
        if args.query:
            results = search_by_text(
                args.query, embeddings_output_file, api_client, 
                top_k=args.top_k, threshold=args.threshold
            )
            
            print("\n搜索结果:")
            formatted_results = format_article_results(results)
            print(formatted_results)
        
        if args.interactive:
            interactive_search(embeddings_output_file, api_client)
            
        # 查询完成后退出
        return
    
    # 处理提取和嵌入生成模式
    # 设置输出文件路径
    info_output_file = args.output or "article_info.json"
    
    # 处理输入
    if os.path.isdir(args.input):
        # 处理目录
        print(f"正在处理目录: {args.input}")
        info_list = process_directory(args.input, args.pattern)
        if not info_list:
            print("错误: 在目录中未找到有效文件或无法提取有效信息")
            sys.exit(1)
            
        save_info_to_file(info_list, info_output_file)
        
        # 创建嵌入向量
        create_embeddings_from_info(info_list, embeddings_output_file, api_client)
    else:
        # 处理单个文件
        print(f"正在处理文件: {args.input}")
        file_info = extract_info_from_file(args.input)
        if file_info["combined_info"]:
            save_info_to_file([file_info], info_output_file)
            create_embeddings_from_info([file_info], embeddings_output_file, api_client)
        else:
            print(f"错误: 无法从文件 {args.input} 中提取有效信息")
            sys.exit(1)
    
    # 执行查询搜索
    if args.query:
        results = search_by_text(
            args.query, embeddings_output_file, api_client, 
            top_k=args.top_k, threshold=args.threshold
        )
        
        print("\n搜索结果:")
        formatted_results = format_article_results(results)
        print(formatted_results)
    
    # 启动交互式搜索
    if args.interactive:
        interactive_search(embeddings_output_file, api_client)


def launch_gui():
    """
    启动图形用户界面
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, ttk, scrolledtext, messagebox
    except ImportError:
        print("错误: 无法导入tkinter模块，请确保已安装Python的tkinter支持")
        return

    # 初始化API客户端
    api_client = None
    try:
        from embed.text_processor import initialize_api_client
        api_client = initialize_api_client()
        if not api_client:
            answer = messagebox.askquestion("警告", 
                "无法初始化API客户端，可能是API密钥配置问题。\n是否继续以测试模式运行？\n(无法进行嵌入和搜索功能)")
            if answer != 'yes':
                return
    except ImportError:
        answer = messagebox.askquestion("警告", 
            "无法导入initialize_api_client。\n是否继续以测试模式运行？\n(无法进行嵌入和搜索功能)")
        if answer != 'yes':
            return

    # 测试模式标志
    test_mode = api_client is None

    # 创建主窗口
    root = tk.Tk()
    root.title("标题和摘要提取器" + (" [测试模式]" if test_mode else ""))
    root.geometry("800x600")
    root.minsize(700, 500)

    # 创建主框架
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # 创建输入选择区域
    input_frame = ttk.LabelFrame(main_frame, text="输入选择", padding=5)
    input_frame.pack(fill=tk.X, pady=5)

    input_var = tk.StringVar()
    input_entry = ttk.Entry(input_frame, textvariable=input_var, width=60)
    input_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def select_input():
        file_path = filedialog.askopenfilename(
            title="选择XML文件",
            filetypes=[("XML文件", "*.xml"), ("所有文件", "*.*")]
        )
        if file_path:
            input_var.set(file_path)

    def select_directory():
        dir_path = filedialog.askdirectory(title="选择包含XML文件的目录")
        if dir_path:
            input_var.set(dir_path)

    input_file_btn = ttk.Button(input_frame, text="选择文件", command=select_input)
    input_file_btn.pack(side=tk.LEFT, padx=5)

    input_dir_btn = ttk.Button(input_frame, text="选择目录", command=select_directory)
    input_dir_btn.pack(side=tk.LEFT, padx=5)

    # 创建输出选择区域
    output_frame = ttk.LabelFrame(main_frame, text="输出设置", padding=5)
    output_frame.pack(fill=tk.X, pady=5)

    output_var = tk.StringVar(value="article_info.json")
    output_entry = ttk.Entry(output_frame, textvariable=output_var, width=50)
    output_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def select_output():
        file_path = filedialog.asksaveasfilename(
            title="保存信息文件",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            output_var.set(file_path)

    output_btn = ttk.Button(output_frame, text="选择文件", command=select_output)
    output_btn.pack(side=tk.LEFT, padx=5)

    embeddings_var = tk.StringVar(value="article_embeddings.json")
    embeddings_label = ttk.Label(output_frame, text="嵌入向量文件:")
    embeddings_label.pack(side=tk.LEFT, padx=5)
    embeddings_entry = ttk.Entry(output_frame, textvariable=embeddings_var, width=30)
    embeddings_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    # 如果处于测试模式，禁用嵌入向量相关控件
    if test_mode:
        embeddings_entry.configure(state="disabled")

    # 创建参数设置区域
    param_frame = ttk.LabelFrame(main_frame, text="参数设置", padding=5)
    param_frame.pack(fill=tk.X, pady=5)

    ttk.Label(param_frame, text="文件匹配模式:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
    pattern_var = tk.StringVar(value="*.xml")
    pattern_entry = ttk.Entry(param_frame, textvariable=pattern_var, width=15)
    pattern_entry.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)

    ttk.Label(param_frame, text="Top-K:").grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
    topk_var = tk.IntVar(value=5)
    topk_entry = ttk.Spinbox(param_frame, from_=1, to=20, textvariable=topk_var, width=5)
    topk_entry.grid(row=0, column=3, padx=5, pady=2, sticky=tk.W)
    
    # 如果处于测试模式，禁用搜索相关控件
    if test_mode:
        topk_entry.configure(state="disabled")

    ttk.Label(param_frame, text="相似度阈值:").grid(row=0, column=4, padx=5, pady=2, sticky=tk.W)
    threshold_var = tk.DoubleVar(value=0.5)
    threshold_entry = ttk.Spinbox(param_frame, from_=0.0, to=1.0, increment=0.05, textvariable=threshold_var, width=5)
    threshold_entry.grid(row=0, column=5, padx=5, pady=2, sticky=tk.W)
    
    # 如果处于测试模式，禁用搜索相关控件
    if test_mode:
        threshold_entry.configure(state="disabled")

    # 创建操作按钮区域
    action_frame = ttk.Frame(main_frame)
    action_frame.pack(fill=tk.X, pady=5)

    # 创建摘要显示和搜索区域
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=5)

    # 摘要显示页面
    extract_tab = ttk.Frame(notebook, padding=5)
    notebook.add(extract_tab, text="提取结果")

    extract_text = scrolledtext.ScrolledText(extract_tab, wrap=tk.WORD)
    extract_text.pack(fill=tk.BOTH, expand=True)

    # 搜索页面
    search_tab = ttk.Frame(notebook, padding=5)
    notebook.add(search_tab, text="搜索")

    search_top_frame = ttk.Frame(search_tab)
    search_top_frame.pack(fill=tk.X, pady=5)

    ttk.Label(search_top_frame, text="搜索查询:").pack(side=tk.LEFT, padx=5)
    query_var = tk.StringVar()
    query_entry = ttk.Entry(search_top_frame, textvariable=query_var, width=50)
    query_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    # 如果处于测试模式，禁用搜索相关控件
    if test_mode:
        query_entry.configure(state="disabled")

    search_result_text = scrolledtext.ScrolledText(search_tab, wrap=tk.WORD)
    search_result_text.pack(fill=tk.BOTH, expand=True, pady=5)

    # 状态栏
    status_var = tk.StringVar(value="就绪" + (" (测试模式 - 仅提取功能可用)" if test_mode else ""))
    status_bar = ttk.Label(main_frame, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # 功能实现
    def update_status(message):
        status_var.set(message + (" (测试模式)" if test_mode else ""))
        root.update_idletasks()

    def show_info_list(info_list):
        extract_text.delete(1.0, tk.END)
        for i, info in enumerate(info_list):
            extract_text.insert(tk.END, f"=== 文档 {i+1} ===\n")
            if info.get("title"):
                extract_text.insert(tk.END, f"标题: {info['title']}\n\n")
            if info.get("abstract"):
                extract_text.insert(tk.END, f"摘要: {info['abstract']}\n\n")
            if info.get("file_path"):
                extract_text.insert(tk.END, f"文件: {info['file_path']}\n")
            if info.get("metadata"):
                meta_str = ", ".join([f"{k}: {v}" for k, v in info['metadata'].items()])
                extract_text.insert(tk.END, f"元数据: {meta_str}\n")
            extract_text.insert(tk.END, "\n" + "-"*50 + "\n\n")

    def extract_action():
        input_path = input_var.get()
        if not input_path:
            messagebox.showerror("错误", "请选择输入文件或目录")
            return

        output_file = output_var.get()
        pattern = pattern_var.get()

        update_status(f"正在处理 {input_path}...")
        try:
            if os.path.isdir(input_path):
                info_list = process_directory(input_path, pattern)
            else:
                file_info = extract_info_from_file(input_path)
                info_list = [file_info] if file_info["combined_info"] else []

            if not info_list:
                messagebox.showwarning("警告", "未提取到任何有效信息")
                update_status("提取完成，但未找到有效信息")
                return

            save_info_to_file(info_list, output_file)
            show_info_list(info_list)
            
            # 如果有API客户端且不是测试模式，则创建嵌入向量
            if api_client and not test_mode:
                embeddings_file = embeddings_var.get()
                create_embeddings_from_info(info_list, embeddings_file, api_client)
                update_status(f"已成功提取 {len(info_list)} 条记录并保存到 {output_file}，嵌入向量已生成")
            else:
                update_status(f"已成功提取 {len(info_list)} 条记录并保存到 {output_file}")
            
            messagebox.showinfo("成功", f"已成功提取 {len(info_list)} 条记录")
            notebook.select(extract_tab)
        except Exception as e:
            messagebox.showerror("错误", f"处理失败: {str(e)}")
            update_status("处理失败")

    def search_action():
        # 如果处于测试模式，显示提示并返回
        if test_mode:
            messagebox.showinfo("测试模式", "搜索功能在测试模式下不可用，需要有效的API客户端")
            return
            
        query = query_var.get()
        if not query:
            messagebox.showerror("错误", "请输入搜索查询")
            return

        embeddings_file = embeddings_var.get()
        if not os.path.exists(embeddings_file):
            messagebox.showerror("错误", f"嵌入向量文件不存在: {embeddings_file}")
            return

        top_k = topk_var.get()
        threshold = threshold_var.get()

        update_status(f"正在搜索: {query}...")
        try:
            results = search_by_text(
                query, embeddings_file, api_client, 
                top_k=top_k, threshold=threshold
            )
            
            formatted_results = format_article_results(results)
            search_result_text.delete(1.0, tk.END)
            search_result_text.insert(tk.END, formatted_results)
            
            update_status(f"搜索完成，找到 {len(results)} 个结果")
            notebook.select(search_tab)
        except Exception as e:
            messagebox.showerror("错误", f"搜索失败: {str(e)}")
            update_status("搜索失败")

    # 添加操作按钮
    extract_btn = ttk.Button(action_frame, text="提取信息" + ("" if test_mode else "并创建嵌入"), command=extract_action)
    extract_btn.pack(side=tk.LEFT, padx=5)

    search_btn = ttk.Button(search_top_frame, text="搜索", command=search_action)
    search_btn.pack(side=tk.LEFT, padx=5)
    
    # 如果处于测试模式，禁用搜索按钮
    if test_mode:
        search_btn.configure(state="disabled")
        
    # 添加测试模式提示
    if test_mode:
        test_label = ttk.Label(main_frame, text="测试模式：仅提取功能可用，搜索功能需要API客户端", 
                              foreground="red", font=("", 10, "bold"))
        test_label.pack(side=tk.TOP, pady=5)

    # 运行GUI主循环
    root.mainloop()


def extract_and_create_embeddings(
    input_path: str,
    output_file: str,
    api_client=None,
    model: str = "doubao-embedding-text-240715",
    file_pattern: str = "*.xml",
    batch_size: int = 10
) -> bool:
    """
    从XML文件中提取文本并生成嵌入向量的整合函数
    
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
    
    # 提取文章信息
    info_list = []
    if os.path.isdir(input_path):
        info_list = process_directory(input_path, file_pattern)
    elif os.path.isfile(input_path):
        file_info = extract_info_from_file(input_path)
        if file_info["combined_info"]:
            info_list = [file_info]
    else:
        print(f"错误: 路径不存在 {input_path}")
        return False
    
    if not info_list:
        print("未找到文章信息")
        return False
    
    print(f"共提取了 {len(info_list)} 个文章信息")
    
    # 生成嵌入向量
    success = create_embeddings_from_info(
        info_list, output_file, api_client, model, batch_size
    )
    
    return success


if __name__ == "__main__":
    main() 