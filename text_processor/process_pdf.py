import os
import sys
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("pdf_processor")

# 添加父目录到路径以便导入grobid_processor
current_dir = Path(__file__).parent.absolute()
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

from grobid_client_python.grobid_processor import GrobidProcessor

# 添加embed目录到路径以便导入相关模块
embed_dir = os.path.join(parent_dir, "embed")
if embed_dir not in sys.path:
    sys.path.append(str(embed_dir))

# 尝试导入嵌入相关模块
try:
    from embed.abstract_extractor import extract_and_create_embeddings as extract_abstracts
    from embed.text_processor import extract_and_create_embeddings as extract_texts
    from embed.text_processor import initialize_api_client
except ImportError as e:
    logger.warning(f"无法导入嵌入模块: {e}")
    logger.warning("摘要和正文的嵌入功能将不可用")
    extract_abstracts = None
    extract_texts = None
    initialize_api_client = None

def process_pdf(input_path):
    """
    处理用户指定目录下的PDF文件
    
    参数:
        input_path: 用户指定的PDF文件或文件夹路径
    
    返回:
        bool: 处理是否成功
    """
    # 验证输入路径
    if not os.path.exists(input_path):
        logger.error(f"输入路径不存在: {input_path}")
        return False
    
    # 创建输出目录（在text_processor目录下）
    output_dir = os.path.join(current_dir, "grobid_xml_output")
    final_dir = os.path.join(current_dir, "processed_output")
    
    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)
    
    logger.info(f"处理PDF: {input_path}")
    logger.info(f"XML输出目录: {output_dir}")
    logger.info(f"最终处理结果目录: {final_dir}")
    
    # 如果input_path是文件，则创建临时目录处理单个文件
    if os.path.isfile(input_path):
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制PDF文件到临时目录
            pdf_filename = os.path.basename(input_path)
            temp_pdf_path = os.path.join(temp_dir, pdf_filename)
            shutil.copy(input_path, temp_pdf_path)
            
            # 更新输入路径为临时目录
            input_path = temp_dir
            
            # 处理PDF
            return _run_processor(input_path, output_dir, final_dir)
    else:
        # 直接处理目录
        return _run_processor(input_path, output_dir, final_dir)

def _run_processor(input_path, output_dir, final_dir):
    """内部函数，运行GrobidProcessor进行处理"""
    # 创建处理器实例
    processor = GrobidProcessor(logger=logger.info)
    
    # 执行处理
    success = processor.process_batch(
        input_path=input_path,
        output_path=output_dir,
        final_output_path=final_dir,
        grobid_client="grobid_client",  # GROBID客户端路径
        concurrency=100,                # 并发数
        include_raw_citations=True,     # 是否保留原始引用
        segment_sentences=True,         # 是否进行句子分割
        use_ascii_only=True             # 是否只使用ASCII字符
    )
    
    if success:
        logger.info("PDF处理成功完成")
        # 如果处理成功，则进行摘要和正文的嵌入处理
        if create_embeddings(final_dir):
            logger.info("摘要和正文嵌入处理成功")
        else:
            logger.error("摘要和正文嵌入处理失败")
    else:
        logger.error("PDF处理失败")
        
    return success

def create_embeddings(processed_dir):
    """
    为处理好的文件创建摘要和正文的嵌入向量
    
    参数:
        processed_dir: 处理后的XML文件目录
        
    返回:
        bool: 处理是否成功
    """
    if extract_abstracts is None or extract_texts is None or initialize_api_client is None:
        logger.error("嵌入功能不可用，请确保正确安装和导入了embed模块")
        return False
    
    # 初始化API客户端
    api_client = initialize_api_client()
    if not api_client:
        logger.error("API客户端初始化失败，无法创建嵌入向量")
        return False
    
    # 创建嵌入向量输出目录
    embeddings_dir = os.path.join(current_dir, "embeddings")
    os.makedirs(embeddings_dir, exist_ok=True)
    
    # 设置摘要和正文的嵌入向量输出文件
    abstract_embeddings_file = os.path.join(embeddings_dir, "abstract_embeddings.json")
    fulltext_embeddings_file = os.path.join(embeddings_dir, "fulltext_embeddings.json")
    
    logger.info("开始创建摘要嵌入向量...")
    abstract_success = False
    fulltext_success = False
    
    try:
        # 创建摘要嵌入向量
        abstract_success = extract_abstracts(
            processed_dir,
            abstract_embeddings_file,
            api_client=api_client,
            file_pattern="*.xml"
        )
        
        if abstract_success:
            logger.info(f"摘要嵌入向量创建成功，保存到: {abstract_embeddings_file}")
        else:
            logger.error("摘要嵌入向量创建失败")
        
        # 创建正文嵌入向量
        logger.info("开始创建正文嵌入向量...")
        fulltext_success = extract_texts(
            processed_dir,
            fulltext_embeddings_file,
            api_client=api_client,
            file_pattern="*.xml"
        )
        
        if fulltext_success:
            logger.info(f"正文嵌入向量创建成功，保存到: {fulltext_embeddings_file}")
        else:
            logger.error("正文嵌入向量创建失败")
        
    except Exception as e:
        logger.error(f"创建嵌入向量时出错: {e}")
        return False
    
    return abstract_success and fulltext_success

def select_and_process_directory():
    """让用户选择目录并处理其中的所有PDF文件"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    # 显示文件夹选择对话框
    input_dir = filedialog.askdirectory(title="选择包含PDF文件的文件夹")
    
    if not input_dir:
        print("未选择任何文件夹，操作已取消")
        return False
    
    # 检查目录中是否有PDF文件
    has_pdf = False
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf'):
            has_pdf = True
            break
    
    if not has_pdf:
        messagebox.showwarning("警告", f"所选文件夹 {input_dir} 中没有找到PDF文件")
        return False
    
    # 处理选中的目录
    print(f"开始处理目录: {input_dir}")
    return process_pdf(input_dir)

def select_and_process_file():
    """让用户选择单个PDF文件并处理"""
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    # 显示文件选择对话框
    input_file = filedialog.askopenfilename(
        title="选择PDF文件",
        filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
    )
    
    if not input_file:
        print("未选择任何文件，操作已取消")
        return False
    
    # 处理选中的文件
    print(f"开始处理文件: {input_file}")
    return process_pdf(input_file)

def process_and_embed(input_path=None):
    """
    处理PDF并创建嵌入向量（可从外部调用的主函数）
    
    参数:
        input_path: 输入路径，如果为None则通过界面选择
        
    返回:
        bool: 处理是否成功
    """
    if input_path:
        return process_pdf(input_path)
    else:
        # 显示选择界面
        print("PDF文献处理工具")
        print("1. 处理单个PDF文件")
        print("2. 处理整个目录中的PDF文件")
        print("q. 退出")
        
        choice = input("请选择操作 [1/2/q]: ").lower()
        
        if choice == '1':
            return select_and_process_file()
        elif choice == '2':
            return select_and_process_directory()
        else:
            print("操作已取消")
            return False

if __name__ == "__main__":
    # 从命令行获取输入路径，或提示用户选择
    if len(sys.argv) > 1:
        # 使用命令行参数
        input_path = sys.argv[1]
        success = process_pdf(input_path)
    else:
        # 显示选择界面
        print("PDF文献处理工具")
        print("1. 处理单个PDF文件")
        print("2. 处理整个目录中的PDF文件")
        print("q. 退出")
        
        choice = input("请选择操作 [1/2/q]: ").lower()
        
        if choice == '1':
            success = select_and_process_file()
        elif choice == '2':
            success = select_and_process_directory()
        else:
            print("操作已取消")
            sys.exit(0)
    
    # 根据处理结果设置退出代码
    sys.exit(0 if success else 1)

