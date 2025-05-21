#!/usr/bin/env python3
"""
集成工作流程：连接PDF处理和大纲处理步骤
1. 首先处理PDF文献，生成XML文件和嵌入向量
2. 然后处理用户输入的大纲，进行分解和关键词检索
3. 将检索结果与大纲进行匹配和整合
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("integrated_workflow")

# 添加相关模块路径
current_dir = Path(__file__).parent.absolute()
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))
sys.path.append(str(current_dir))

# 导入PDF处理和大纲处理模块
try:
    from process_pdf import process_and_embed
    from outline_processor import OutlineProcessor
except ImportError as e:
    logger.error(f"导入模块出错: {e}")
    logger.error("请确保已安装所有必要的依赖和模块")
    sys.exit(1)


class WorkflowManager:
    """工作流程管理器，连接PDF处理和大纲处理"""
    
    def __init__(self):
        """初始化工作流程管理器"""
        # 初始化状态
        self.pdf_processed = False
        self.outline_processed = False
        
        # 检查输出目录
        self.output_dir = os.path.join(current_dir, "workflow_results")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def process_pdfs(self, input_path):
        """
        处理PDF文献
        
        参数:
            input_path: PDF文件或目录路径
            
        返回:
            bool: 处理是否成功
        """
        logger.info(f"开始处理PDF文献: {input_path}")
        success = process_and_embed(input_path)
        
        if success:
            logger.info("PDF文献处理成功")
            self.pdf_processed = True
        else:
            logger.error("PDF文献处理失败")
            self.pdf_processed = False
        
        return success
    
    def process_outline(self, outline_text):
        """
        处理大纲
        
        参数:
            outline_text: 大纲文本
            
        返回:
            str: 结果文件路径，处理失败则返回None
        """
        if not self.pdf_processed:
            logger.warning("警告: 尚未处理PDF文献，大纲处理可能无法找到相关文献")
        
        logger.info("开始处理大纲...")
        try:
            # 初始化大纲处理器
            processor = OutlineProcessor()
            
            # 处理大纲
            result_file = processor.process_outline(outline_text)
            
            logger.info(f"大纲处理成功，结果保存在: {result_file}")
            self.outline_processed = True
            return result_file
        except Exception as e:
            logger.error(f"大纲处理失败: {e}")
            self.outline_processed = False
            return None
    
    def run_complete_workflow(self, pdf_path, outline_text):
        """
        运行完整工作流程
        
        参数:
            pdf_path: PDF文件或目录路径
            outline_text: 大纲文本
            
        返回:
            dict: 包含处理结果的字典
        """
        results = {
            "pdf_processing": {
                "success": False,
                "message": ""
            },
            "outline_processing": {
                "success": False,
                "result_file": None,
                "message": ""
            }
        }
        
        # 步骤1: 处理PDF文献
        try:
            pdf_success = self.process_pdfs(pdf_path)
            results["pdf_processing"]["success"] = pdf_success
            results["pdf_processing"]["message"] = "PDF文献处理成功" if pdf_success else "PDF文献处理失败"
        except Exception as e:
            results["pdf_processing"]["success"] = False
            results["pdf_processing"]["message"] = f"PDF文献处理出错: {str(e)}"
            return results
        
        # 如果PDF处理失败，不继续进行大纲处理
        if not pdf_success:
            return results
        
        # 步骤2: 处理大纲
        try:
            result_file = self.process_outline(outline_text)
            results["outline_processing"]["success"] = result_file is not None
            results["outline_processing"]["result_file"] = result_file
            
            if result_file:
                results["outline_processing"]["message"] = f"大纲处理成功，结果保存在: {result_file}"
            else:
                results["outline_processing"]["message"] = "大纲处理失败"
        except Exception as e:
            results["outline_processing"]["success"] = False
            results["outline_processing"]["message"] = f"大纲处理出错: {str(e)}"
        
        return results


class WorkflowApp:
    """集成工作流程应用界面"""
    
    def __init__(self, root):
        """初始化应用界面"""
        self.root = root
        self.root.title("文献处理与大纲分析工具")
        self.root.geometry("1000x800")
        
        # 初始化工作流程管理器
        self.workflow_manager = WorkflowManager()
        
        self.create_widgets()
    
    def create_widgets(self):
        """创建界面组件"""
        # 创建标签页控件
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建PDF处理页面
        self.pdf_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.pdf_frame, text="步骤1: PDF文献处理")
        self.create_pdf_page()
        
        # 创建大纲处理页面
        self.outline_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.outline_frame, text="步骤2: 大纲处理")
        self.create_outline_page()
        
        # 创建一键处理页面
        self.workflow_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.workflow_frame, text="一键处理")
        self.create_workflow_page()
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 自定义日志处理器类
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
        
        # 为所有日志输出配置处理器
        text_handler = TextHandler(self.workflow_log)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        text_handler.setFormatter(formatter)
        logger.addHandler(text_handler)
    
    def create_pdf_page(self):
        """创建PDF处理页面"""
        # PDF输入框架
        input_frame = ttk.LabelFrame(self.pdf_frame, text="PDF输入", padding=10)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="PDF文件或目录:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.pdf_path_var = tk.StringVar()
        pdf_entry = ttk.Entry(input_frame, textvariable=self.pdf_path_var, width=50)
        pdf_entry.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        
        browse_button = ttk.Button(input_frame, text="浏览...", command=self.browse_pdf)
        browse_button.grid(row=0, column=2, padx=5)
        
        # 操作框架
        action_frame = ttk.Frame(self.pdf_frame, padding=10)
        action_frame.pack(fill=tk.X, pady=5)
        
        self.process_pdf_button = ttk.Button(action_frame, text="处理PDF", command=self.process_pdf)
        self.process_pdf_button.pack(side=tk.LEFT, padx=5)
        
        # 日志框架
        log_frame = ttk.LabelFrame(self.pdf_frame, text="处理日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.pdf_log = scrolledtext.ScrolledText(log_frame)
        self.pdf_log.pack(fill=tk.BOTH, expand=True)
        self.pdf_log.config(state=tk.DISABLED)
    
    def create_outline_page(self):
        """创建大纲处理页面"""
        # 大纲输入框架
        input_frame = ttk.LabelFrame(self.outline_frame, text="大纲输入", padding=10)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="请输入或加载大纲:").pack(anchor=tk.W)
        
        buttons_frame = ttk.Frame(input_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        load_button = ttk.Button(buttons_frame, text="加载大纲文件", command=self.load_outline)
        load_button.pack(side=tk.LEFT, padx=5)
        
        clear_button = ttk.Button(buttons_frame, text="清空", command=self.clear_outline)
        clear_button.pack(side=tk.LEFT, padx=5)
        
        self.outline_text = scrolledtext.ScrolledText(input_frame, height=10)
        self.outline_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 操作框架
        action_frame = ttk.Frame(self.outline_frame, padding=10)
        action_frame.pack(fill=tk.X, pady=5)
        
        self.process_outline_button = ttk.Button(action_frame, text="处理大纲", command=self.process_outline)
        self.process_outline_button.pack(side=tk.LEFT, padx=5)
        
        # 结果框架
        result_frame = ttk.LabelFrame(self.outline_frame, text="处理日志", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.outline_log = scrolledtext.ScrolledText(result_frame)
        self.outline_log.pack(fill=tk.BOTH, expand=True)
        self.outline_log.config(state=tk.DISABLED)
    
    def create_workflow_page(self):
        """创建一键处理页面"""
        # PDF输入框架
        pdf_frame = ttk.LabelFrame(self.workflow_frame, text="PDF输入", padding=10)
        pdf_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pdf_frame, text="PDF文件或目录:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.workflow_pdf_path_var = tk.StringVar()
        pdf_entry = ttk.Entry(pdf_frame, textvariable=self.workflow_pdf_path_var, width=50)
        pdf_entry.grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)
        
        browse_button = ttk.Button(pdf_frame, text="浏览...", command=self.browse_workflow_pdf)
        browse_button.grid(row=0, column=2, padx=5)
        
        # 大纲输入框架
        outline_frame = ttk.LabelFrame(self.workflow_frame, text="大纲输入", padding=10)
        outline_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(outline_frame, text="请输入或加载大纲:").pack(anchor=tk.W)
        
        buttons_frame = ttk.Frame(outline_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        load_button = ttk.Button(buttons_frame, text="加载大纲文件", command=self.load_workflow_outline)
        load_button.pack(side=tk.LEFT, padx=5)
        
        clear_button = ttk.Button(buttons_frame, text="清空", command=self.clear_workflow_outline)
        clear_button.pack(side=tk.LEFT, padx=5)
        
        self.workflow_outline_text = scrolledtext.ScrolledText(outline_frame, height=10)
        self.workflow_outline_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 操作框架
        action_frame = ttk.Frame(self.workflow_frame, padding=10)
        action_frame.pack(fill=tk.X, pady=5)
        
        self.run_workflow_button = ttk.Button(action_frame, text="一键处理", command=self.run_workflow)
        self.run_workflow_button.pack(side=tk.LEFT, padx=5)
        
        # 日志框架
        log_frame = ttk.LabelFrame(self.workflow_frame, text="处理日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.workflow_log = scrolledtext.ScrolledText(log_frame)
        self.workflow_log.pack(fill=tk.BOTH, expand=True)
        self.workflow_log.config(state=tk.DISABLED)
    
    def browse_pdf(self):
        """浏览选择PDF文件或目录"""
        # 先尝试选择文件
        file_path = filedialog.askopenfilename(
            title="选择PDF文件",
            filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        # 如果取消选择文件，则尝试选择目录
        if not file_path:
            dir_path = filedialog.askdirectory(title="选择包含PDF文件的目录")
            if dir_path:
                self.pdf_path_var.set(dir_path)
        else:
            self.pdf_path_var.set(file_path)
    
    def browse_workflow_pdf(self):
        """浏览选择工作流PDF文件或目录"""
        # 先尝试选择文件
        file_path = filedialog.askopenfilename(
            title="选择PDF文件",
            filetypes=[("PDF文件", "*.pdf"), ("所有文件", "*.*")]
        )
        
        # 如果取消选择文件，则尝试选择目录
        if not file_path:
            dir_path = filedialog.askdirectory(title="选择包含PDF文件的目录")
            if dir_path:
                self.workflow_pdf_path_var.set(dir_path)
        else:
            self.workflow_pdf_path_var.set(file_path)
    
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
                    self.outline_text.delete("1.0", tk.END)
                    self.outline_text.insert(tk.END, content)
            except Exception as e:
                messagebox.showerror("错误", f"无法读取文件: {str(e)}")
    
    def load_workflow_outline(self):
        """加载工作流大纲文件"""
        file_path = filedialog.askopenfilename(
            title="选择大纲文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.workflow_outline_text.delete("1.0", tk.END)
                    self.workflow_outline_text.insert(tk.END, content)
            except Exception as e:
                messagebox.showerror("错误", f"无法读取文件: {str(e)}")
    
    def clear_outline(self):
        """清空大纲输入"""
        self.outline_text.delete("1.0", tk.END)
    
    def clear_workflow_outline(self):
        """清空工作流大纲输入"""
        self.workflow_outline_text.delete("1.0", tk.END)
    
    def process_pdf(self):
        """处理PDF文件或目录"""
        pdf_path = self.pdf_path_var.get()
        if not pdf_path:
            messagebox.showwarning("警告", "请先选择PDF文件或目录")
            return
        
        # 禁用按钮，防止重复点击
        self.process_pdf_button.config(state=tk.DISABLED)
        self.status_var.set("处理PDF中...")
        
        # 清空日志
        self.pdf_log.config(state=tk.NORMAL)
        self.pdf_log.delete("1.0", tk.END)
        self.pdf_log.config(state=tk.DISABLED)
        
        # 添加日志处理器
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
        
        # 配置日志到PDF页面
        pdf_handler = TextHandler(self.pdf_log)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        pdf_handler.setFormatter(formatter)
        logger.addHandler(pdf_handler)
        
        # 在单独的线程中处理PDF
        def process_thread():
            try:
                success = self.workflow_manager.process_pdfs(pdf_path)
                
                # 更新UI
                self.root.after(0, lambda: self.after_pdf_processing(success))
            except Exception as e:
                logger.error(f"PDF处理出错: {str(e)}")
                self.root.after(0, lambda: self.after_pdf_processing(False, str(e)))
            finally:
                # 移除日志处理器
                logger.removeHandler(pdf_handler)
        
        # 启动处理线程
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()
    
    def after_pdf_processing(self, success, error_msg=None):
        """PDF处理完成后的操作"""
        self.process_pdf_button.config(state=tk.NORMAL)
        
        if success:
            self.status_var.set("PDF处理完成")
            messagebox.showinfo("成功", "PDF处理成功完成！")
        else:
            self.status_var.set("PDF处理失败")
            error_text = f"处理失败: {error_msg}" if error_msg else "处理失败"
            messagebox.showerror("错误", error_text)
    
    def process_outline(self):
        """处理大纲"""
        outline_text = self.outline_text.get("1.0", tk.END).strip()
        if not outline_text:
            messagebox.showwarning("警告", "请先输入或加载大纲")
            return
        
        # 检查是否已处理PDF
        if not self.workflow_manager.pdf_processed:
            answer = messagebox.askyesno(
                "警告", 
                "尚未处理PDF文献，可能无法找到相关文献。是否继续处理大纲？"
            )
            if not answer:
                return
        
        # 禁用按钮，防止重复点击
        self.process_outline_button.config(state=tk.DISABLED)
        self.status_var.set("处理大纲中...")
        
        # 清空日志
        self.outline_log.config(state=tk.NORMAL)
        self.outline_log.delete("1.0", tk.END)
        self.outline_log.config(state=tk.DISABLED)
        
        # 添加日志处理器
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
        
        # 配置日志到大纲页面
        outline_handler = TextHandler(self.outline_log)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        outline_handler.setFormatter(formatter)
        logger.addHandler(outline_handler)
        
        # 在单独的线程中处理大纲
        def process_thread():
            try:
                result_file = self.workflow_manager.process_outline(outline_text)
                
                # 更新UI
                self.root.after(0, lambda: self.after_outline_processing(result_file))
            except Exception as e:
                logger.error(f"大纲处理出错: {str(e)}")
                self.root.after(0, lambda: self.after_outline_processing(None, str(e)))
            finally:
                # 移除日志处理器
                logger.removeHandler(outline_handler)
        
        # 启动处理线程
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()
    
    def after_outline_processing(self, result_file, error_msg=None):
        """大纲处理完成后的操作"""
        self.process_outline_button.config(state=tk.NORMAL)
        
        if result_file:
            self.status_var.set("大纲处理完成")
            messagebox.showinfo("成功", f"大纲处理成功完成！\n结果已保存到: {result_file}")
        else:
            self.status_var.set("大纲处理失败")
            error_text = f"处理失败: {error_msg}" if error_msg else "处理失败"
            messagebox.showerror("错误", error_text)
    
    def run_workflow(self):
        """运行完整工作流程"""
        pdf_path = self.workflow_pdf_path_var.get()
        outline_text = self.workflow_outline_text.get("1.0", tk.END).strip()
        
        if not pdf_path:
            messagebox.showwarning("警告", "请先选择PDF文件或目录")
            return
        
        if not outline_text:
            messagebox.showwarning("警告", "请先输入或加载大纲")
            return
        
        # 禁用按钮，防止重复点击
        self.run_workflow_button.config(state=tk.DISABLED)
        self.status_var.set("正在运行完整工作流程...")
        
        # 清空日志
        self.workflow_log.config(state=tk.NORMAL)
        self.workflow_log.delete("1.0", tk.END)
        self.workflow_log.config(state=tk.DISABLED)
        
        # 在单独的线程中运行工作流程
        def workflow_thread():
            try:
                results = self.workflow_manager.run_complete_workflow(pdf_path, outline_text)
                
                # 更新UI
                self.root.after(0, lambda: self.after_workflow(results))
            except Exception as e:
                logger.error(f"工作流程出错: {str(e)}")
                self.root.after(0, lambda: self.after_workflow(None, str(e)))
        
        # 启动处理线程
        thread = threading.Thread(target=workflow_thread)
        thread.daemon = True
        thread.start()
    
    def after_workflow(self, results, error_msg=None):
        """工作流程完成后的操作"""
        self.run_workflow_button.config(state=tk.NORMAL)
        
        if results:
            # 检查处理结果
            pdf_success = results["pdf_processing"]["success"]
            outline_success = results["outline_processing"]["success"]
            
            if pdf_success and outline_success:
                self.status_var.set("工作流程完成")
                result_file = results["outline_processing"]["result_file"]
                messagebox.showinfo("成功", f"完整工作流程成功完成！\n结果已保存到: {result_file}")
            elif pdf_success:
                self.status_var.set("工作流程部分完成")
                messagebox.showwarning("警告", 
                    f"PDF处理成功，但大纲处理失败。\n{results['outline_processing']['message']}")
            else:
                self.status_var.set("工作流程失败")
                messagebox.showerror("错误", 
                    f"PDF处理失败。\n{results['pdf_processing']['message']}")
        else:
            self.status_var.set("工作流程失败")
            error_text = f"工作流程出错: {error_msg}" if error_msg else "工作流程失败"
            messagebox.showerror("错误", error_text)


def main():
    """主函数"""
    root = tk.Tk()
    app = WorkflowApp(root)
    root.mainloop()


if __name__ == "__main__":
    main() 