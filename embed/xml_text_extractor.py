#!/usr/bin/env python3
"""
XML文本提取器：使用纯文本方式和正则表达式从XML文件中提取<p>标签内容
"""

import os
import re
import glob
import json
import argparse
import sys
from typing import List, Dict, Tuple

# 确保embed包可以被导入
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


def extract_paragraphs_from_file(file_path: str) -> List[str]:
    """
    从XML文件中提取所有<p>标签内容，保留内部标签
    
    Args:
        file_path: XML文件路径
        
    Returns:
        包含所有<p>标签内容的字符串列表
    """
    try:
        # 以纯文本形式读取文件
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 使用正则表达式查找所有<p>和</p>标签之间的内容
        # 支持<p>标签可能带有的属性，用非贪婪模式匹配确保正确匹配嵌套标签
        paragraph_pattern = re.compile(r'<p(?:\s[^>]*)?>((?:.|\n)*?)</p>', re.DOTALL)
        paragraphs = paragraph_pattern.findall(content)
        
        # 打印调试信息
        print(f"从文件 {file_path} 中提取了 {len(paragraphs)} 个段落")
        
        # 返回非空段落
        valid_paragraphs = []
        for p in paragraphs:
            if p.strip():  # 只保留非空段落
                valid_paragraphs.append(p)
            
        if len(valid_paragraphs) < len(paragraphs):
            print(f"跳过了 {len(paragraphs) - len(valid_paragraphs)} 个空段落")
            
        return valid_paragraphs
        
    except Exception as e:
        print(f"处理文件时出错 {file_path}: {e}")
        return []


def extract_paragraphs_with_metadata(file_path: str) -> List[Dict]:
    """
    从XML文件中提取所有<p>标签内容，并保留文件元数据
    
    Args:
        file_path: XML文件路径
        
    Returns:
        包含段落内容和元数据的字典列表
    """
    try:
        paragraphs = extract_paragraphs_from_file(file_path)
        
        # 从文件名中提取元数据
        file_name = os.path.basename(file_path)
        # 尝试从文件名中提取信息
        metadata = {}
        if " - " in file_name:
            parts = file_name.split(" - ")
            if len(parts) >= 3:
                metadata["journal"] = parts[0].strip()
                metadata["year"] = parts[1].strip()
                metadata["author"] = parts[2].split(" ")[0].strip()
                metadata["title"] = " ".join(parts[2:]).split(".")[0].strip()
        
        # 构建结果列表
        result = []
        for i, p in enumerate(paragraphs):
            result.append({
                "paragraph_id": i,
                "content": p,
                "file_path": file_path,
                "file_name": file_name,
                "metadata": metadata
            })
        
        return result
    
    except Exception as e:
        print(f"提取段落元数据时出错 {file_path}: {e}")
        return []


def process_directory(directory: str, file_pattern: str = "*.xml") -> Dict[str, List[str]]:
    """
    处理目录中的所有XML文件
    
    Args:
        directory: 包含XML文件的目录
        file_pattern: 匹配XML文件的glob模式
        
    Returns:
        字典，键为文件名，值为段落文本列表
    """
    if not directory:
        raise ValueError("未指定目录")
    
    result = {}
    file_paths = glob.glob(os.path.join(directory, file_pattern))
    
    for file_path in file_paths:
        file_name = os.path.basename(file_path)
        paragraphs = extract_paragraphs_from_file(file_path)
        result[file_name] = paragraphs
        
    return result


def process_directory_with_metadata(directory: str, file_pattern: str = "*.xml") -> List[Dict]:
    """
    处理目录中的所有XML文件，保留文件元数据
    
    Args:
        directory: 包含XML文件的目录
        file_pattern: 匹配XML文件的glob模式
        
    Returns:
        包含段落内容和元数据的字典列表
    """
    if not directory:
        raise ValueError("未指定目录")
    
    result = []
    file_paths = glob.glob(os.path.join(directory, file_pattern))
    
    for file_path in file_paths:
        paragraphs_with_metadata = extract_paragraphs_with_metadata(file_path)
        result.extend(paragraphs_with_metadata)
        
    return result


def save_paragraphs_to_file(result: dict, output_file: str, format: str = 'json'):
    """
    将提取的段落保存到文件
    
    Args:
        result: 字典，键为文件名，值为段落文本列表
        output_file: 保存输出的文件路径
        format: 输出格式（'json'或'txt'）
    """
    if format == 'json':
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    else:  # txt格式
        with open(output_file, 'w', encoding='utf-8') as f:
            for file_name, paragraphs in result.items():
                f.write(f"=== {file_name} ===\n\n")
                for i, paragraph in enumerate(paragraphs):
                    f.write(f"段落 {i+1}:\n{paragraph}\n\n")


def save_paragraphs_with_metadata(paragraphs: List[Dict], output_file: str):
    """
    将带元数据的段落保存到JSON文件
    
    Args:
        paragraphs: 包含段落内容和元数据的字典列表
        output_file: 保存输出的文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(paragraphs, f, ensure_ascii=False, indent=2)
    
    print(f"保存了 {len(paragraphs)} 条段落记录到 {output_file}")


def main():
    """
    命令行界面
    """
    parser = argparse.ArgumentParser(
        description='使用纯文本和正则表达式从XML文件中提取<p>标签内容'
    )
    
    parser.add_argument(
        '--input', '-i', 
        required=True,
        help='输入XML文件或包含XML文件的目录'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='保存提取段落的输出文件（默认：paragraphs.json）'
    )
    
    parser.add_argument(
        '--pattern', '-p',
        default='*.grobid.tei.xml',
        help='匹配XML文件的模式（默认：*.grobid.tei.xml）'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'txt'],
        default='json',
        help='输出格式（默认：json）'
    )
    
    parser.add_argument(
        '--metadata', '-m',
        action='store_true',
        help='是否包含文件元数据（仅用于JSON格式）'
    )
    
    args = parser.parse_args()
    
    # 处理输入
    if os.path.isdir(args.input):
        if args.metadata:
            result = process_directory_with_metadata(args.input, args.pattern)
            output_file = args.output or "paragraphs_with_metadata.json"
            save_paragraphs_with_metadata(result, output_file)
        else:
            result = process_directory(args.input, args.pattern)
            output_file = args.output or f"paragraphs.{args.format}"
            save_paragraphs_to_file(result, output_file, args.format)
    else:
        # 处理单个文件
        file_name = os.path.basename(args.input)
        if args.metadata:
            paragraphs = extract_paragraphs_with_metadata(args.input)
            output_file = args.output or "paragraphs_with_metadata.json"
            save_paragraphs_with_metadata(paragraphs, output_file)
        else:
            paragraphs = extract_paragraphs_from_file(args.input)
            result = {file_name: paragraphs}
            output_file = args.output or f"paragraphs.{args.format}"
            save_paragraphs_to_file(result, output_file, args.format)
    
    # 打印摘要
    total_paragraphs = 0
    if isinstance(result, dict):
        total_paragraphs = sum(len(paragraphs) for paragraphs in result.values())
    else:
        total_paragraphs = len(result)
    
    print(f"提取完成：从 {len(result) if isinstance(result, dict) else 1} 个文件中提取了 {total_paragraphs} 段文本。")
    print(f"结果已保存至 {output_file}")


# 简单的交互式界面
def interactive():
    """
    提供简单的交互式界面
    """
    print("XML段落提取器 - 纯文本版")
    print("-" * 40)
    
    # 获取输入文件或目录
    input_path = input("请输入XML文件或目录路径: ")
    if not input_path:
        print("未提供有效路径")
        return
    
    # 处理目录
    if os.path.isdir(input_path):
        pattern = input("输入文件匹配模式 (默认: *.grobid.tei.xml): ") or "*.grobid.tei.xml"
        include_metadata = input("是否包含文件元数据? (y/n, 默认n): ").lower() == 'y'
        
        if include_metadata:
            result = process_directory_with_metadata(input_path, pattern)
        else:
            result = process_directory(input_path, pattern)
    # 处理单个文件
    elif os.path.isfile(input_path):
        file_name = os.path.basename(input_path)
        include_metadata = input("是否包含文件元数据? (y/n, 默认n): ").lower() == 'y'
        
        if include_metadata:
            result = extract_paragraphs_with_metadata(input_path)
        else:
            paragraphs = extract_paragraphs_from_file(input_path)
            result = {file_name: paragraphs}
    else:
        print(f"文件或目录不存在: {input_path}")
        return
    
    # 打印摘要
    total_files = 1
    total_paragraphs = 0
    
    if isinstance(result, dict):
        total_files = len(result)
        total_paragraphs = sum(len(paragraphs) for paragraphs in result.values())
    else:
        total_paragraphs = len(result)
    
    print(f"\n找到 {total_files} 个文件，共 {total_paragraphs} 段文本")
    
    # 预览结果
    if total_paragraphs > 0:
        preview = input("是否预览提取到的文本? (y/n, 默认n): ").lower()
        if preview == 'y':
            if isinstance(result, dict):
                for file_name, paragraphs in result.items():
                    print(f"\n文件: {file_name}")
                    for i, p in enumerate(paragraphs[:3]):  # 只显示前3个段落
                        preview_text = p[:100] + "..." if len(p) > 100 else p
                        print(f"  段落 {i+1}: {preview_text}")
                    if len(paragraphs) > 3:
                        print(f"  ... 还有 {len(paragraphs) - 3} 个段落")
            else:
                for i, item in enumerate(result[:5]):  # 只显示前5个条目
                    print(f"\n条目 {i+1}:")
                    print(f"  文件: {item['file_name']}")
                    preview_text = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                    print(f"  内容: {preview_text}")
                if len(result) > 5:
                    print(f"  ... 还有 {len(result) - 5} 个条目")
    
    # 保存结果
    save = input("\n是否保存结果? (y/n, 默认y): ").lower() or 'y'
    if save == 'y':
        if include_metadata:
            format_type = 'json'
            output_file = input(f"输入保存路径 (默认: paragraphs_with_metadata.json): ") or "paragraphs_with_metadata.json"
            save_paragraphs_with_metadata(result, output_file)
        else:
            format_type = input("选择输出格式 (json/txt, 默认json): ").lower() or 'json'
            output_file = input(f"输入保存路径 (默认: paragraphs.{format_type}): ") or f"paragraphs.{format_type}"
            
            if format_type == 'json':
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            else:
                with open(output_file, 'w', encoding='utf-8') as f:
                    if isinstance(result, dict):
                        for file_name, paragraphs in result.items():
                            f.write(f"=== {file_name} ===\n\n")
                            for i, paragraph in enumerate(paragraphs):
                                f.write(f"段落 {i+1}:\n{paragraph}\n\n")
                    else:
                        for i, item in enumerate(result):
                            f.write(f"=== 条目 {i+1} ===\n")
                            f.write(f"文件: {item['file_name']}\n")
                            f.write(f"内容:\n{item['content']}\n\n")
            
        print(f"结果已保存至 {output_file}")


if __name__ == "__main__":
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        main()  # 使用命令行界面
    else:
        interactive()  # 使用交互式界面 