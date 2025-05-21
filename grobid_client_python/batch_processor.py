import os
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import xml.etree.ElementTree as ET
import threading
import glob
import time
import sys

class GrobidBatchProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("GROBID 批量处理工具")
        self.root.geometry("1000x800")
        
        # 创建命名空间变量
        self.xml_namespace = {'tei': 'http://www.tei-c.org/ns/1.0'}
        self.references = {}  # 存储参考文献ID到格式化引用的映射
        # xml_namespace 中的网址 'http://www.tei-c.org/ns/1.0' 是TEI XML标准的命名空间URI
        # TEI (Text Encoding Initiative) 是一个用于数字化文本编码的国际标准
        # 这个URI不是实际可访问的网址,而是一个唯一标识符
        # XML解析器通过这个URI来识别和验证文档使用的是哪个TEI标准版本
        # 这样可以确保XML文档的结构符合TEI规范,并能正确解析文档中的元素和属性
        
        # references字典用于存储从XML中提取的参考文献信息
        # 比如: references = {'ref-1': '作者. 标题. 期刊, 年份'} 
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建路径选择部分
        self.create_path_section()
        
        # 创建处理选项部分
        self.create_options_section()
        
        # 创建日志显示部分
        self.create_log_section()
        
        # 创建按钮部分
        self.create_buttons_section()
        
        # 进度条
        self.progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=600, mode="determinate")
        self.progress.pack(fill=tk.X, pady=10)
        
        # 处理状态
        self.processing = False
    
    def create_path_section(self):
        path_frame = ttk.LabelFrame(self.main_frame, text="路径设置", padding="10")
        path_frame.pack(fill=tk.X, pady=5)
        
        # PDF输入路径
        input_frame = ttk.Frame(path_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text="PDF输入文件夹:").pack(side=tk.LEFT)
        self.input_path = ttk.Entry(input_frame, width=50)
        self.input_path.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(input_frame, text="浏览", command=self.browse_input).pack(side=tk.LEFT)
        
        # XML输出路径
        output_frame = ttk.Frame(path_frame)
        output_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(output_frame, text="XML输出文件夹:").pack(side=tk.LEFT)
        self.output_path = ttk.Entry(output_frame, width=50)
        self.output_path.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(output_frame, text="浏览", command=self.browse_output).pack(side=tk.LEFT)
        
        # 最终处理结果输出路径
        final_output_frame = ttk.Frame(path_frame)
        final_output_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(final_output_frame, text="处理后文件输出文件夹:").pack(side=tk.LEFT)
        self.final_output_path = ttk.Entry(final_output_frame, width=50)
        self.final_output_path.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(final_output_frame, text="浏览", command=self.browse_final_output).pack(side=tk.LEFT)
    
    def create_options_section(self):
        options_frame = ttk.LabelFrame(self.main_frame, text="处理选项", padding="10")
        options_frame.pack(fill=tk.X, pady=5)
        
        # GROBID路径
        grobid_frame = ttk.Frame(options_frame)
        grobid_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(grobid_frame, text="GROBID客户端路径:").pack(side=tk.LEFT)
        self.grobid_client_path = ttk.Entry(grobid_frame, width=50)
        self.grobid_client_path.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        self.grobid_client_path.insert(0, "grobid_client") # 默认值
        
        # 并发数
        concurrency_frame = ttk.Frame(options_frame)
        concurrency_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(concurrency_frame, text="并发数:").pack(side=tk.LEFT)
        self.concurrency = ttk.Entry(concurrency_frame, width=10)
        self.concurrency.pack(side=tk.LEFT, padx=5)
        self.concurrency.insert(0, "300")  # 默认值
        
        # 选项复选框
        self.include_raw_citations_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="保留原始引用", 
                      variable=self.include_raw_citations_var).pack(anchor=tk.W)
        
        self.segment_sentences_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="句子分割", 
                      variable=self.segment_sentences_var).pack(anchor=tk.W)
        
        # 添加ASCII编码选项
        self.use_ascii_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="只使用ASCII字符(删除非ASCII字符)", 
                      variable=self.use_ascii_only_var).pack(anchor=tk.W)
    
    def create_log_section(self):
        log_frame = ttk.LabelFrame(self.main_frame, text="处理日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def create_buttons_section(self):
        buttons_frame = ttk.Frame(self.main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        self.start_button = ttk.Button(buttons_frame, text="开始处理", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(buttons_frame, text="停止处理", command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(buttons_frame, text="清除日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)
    
    def browse_input(self):
        path = filedialog.askdirectory(title="选择PDF输入文件夹")
        if path:
            self.input_path.delete(0, tk.END)
            self.input_path.insert(0, path)
    
    def browse_output(self):
        path = filedialog.askdirectory(title="选择XML输出文件夹")
        if path:
            self.output_path.delete(0, tk.END)
            self.output_path.insert(0, path)
    
    def browse_final_output(self):
        path = filedialog.askdirectory(title="选择处理后文件输出文件夹")
        if path:
            self.final_output_path.delete(0, tk.END)
            self.final_output_path.insert(0, path)
    
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def start_processing(self):
        if self.processing:
            return
        
        # 获取输入和输出路径
        input_path = self.input_path.get()
        output_path = self.output_path.get()
        final_output_path = self.final_output_path.get()
        
        # 验证路径
        if not input_path or not os.path.isdir(input_path):
            messagebox.showerror("错误", "请选择有效的PDF输入文件夹")
            return
        
        if not output_path:
            messagebox.showerror("错误", "请选择XML输出文件夹")
            return
        
        if not final_output_path:
            messagebox.showerror("错误", "请选择处理后文件输出文件夹")
            return
        
        # 创建输出目录（如果不存在）
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(final_output_path, exist_ok=True)
        
        # 更新UI状态
        self.processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 启动处理线程
        self.process_thread = threading.Thread(target=self.process_files, args=(
            input_path, output_path, final_output_path))
        self.process_thread.daemon = True
        self.process_thread.start()
    
    def stop_processing(self):
        if not self.processing:
            return
        
        self.processing = False
        self.log("正在停止处理...")
        self.root.update_idletasks()
    
    def process_files(self, input_path, output_path, final_output_path):
        try:
            # 第一步：使用GROBID处理PDF文件
            self.log("=== 步骤1：使用GROBID处理PDF文件 ===")
            self.run_grobid_processing(input_path, output_path)
            
            if not self.processing:
                self.log("处理已停止")
                self.update_ui_after_processing()
                return
            
            # 第二步：处理生成的XML文件
            self.log("\n=== 步骤2：处理生成的XML文件 ===")
            self.process_xml_files(output_path, final_output_path)
            
            self.log("\n处理完成！")
        except Exception as e:
            self.log(f"处理过程中出错: {str(e)}")
        finally:
            self.update_ui_after_processing()
    
    def update_ui_after_processing(self):
        self.processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.root.update_idletasks()
    
    def run_grobid_processing(self, input_path, output_path):
        grobid_client = self.grobid_client_path.get()
        n_value = self.concurrency.get()
        
        # 构建命令
        cmd = [
            grobid_client,
            "--input", input_path,
            "--output", output_path,
            "--n", n_value
        ]
        
        # 添加选项
        if self.include_raw_citations_var.get():
            cmd.append("--include_raw_citations")
        
        if self.segment_sentences_var.get():
            cmd.append("--segmentSentences")
        
        # 添加service参数（必需）
        cmd.append("processFulltextDocument")
        
        self.log(f"执行命令: {' '.join(cmd)}")
        
        # 确定 grobid_client_python 目录作为工作目录
        # 假设 config.json 位于 batch_processor.py 所在的目录
        process_cwd = os.path.dirname(os.path.abspath(__file__))
        self.log(f"设置 grobid_client 工作目录为: {process_cwd}")

        # 执行命令
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                cwd=process_cwd  # 设置子进程的工作目录
            )
            
            # 实时读取输出
            for line in iter(process.stdout.readline, ''):
                if not self.processing:
                    process.terminate()
                    break
                self.log(line.strip())
            
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0 and self.processing:
                self.log(f"GROBID处理返回错误码: {return_code}")
            
        except Exception as e:
            self.log(f"执行GROBID命令时出错: {str(e)}")
    
    def convert_to_ascii(self, text):
        """将文本转换为ASCII，删除所有非ASCII字符"""
        return ''.join(char for char in text if ord(char) < 128)
    
    def process_xml_files(self, xml_dir, output_dir):
        # 获取所有XML文件
        xml_files = glob.glob(os.path.join(xml_dir, "*.xml"))
        total_files = len(xml_files)
        
        if total_files == 0:
            self.log("没有找到XML文件进行处理")
            return
        
        self.log(f"找到 {total_files} 个XML文件需要处理")
        self.progress['maximum'] = total_files
        
        # 处理每个XML文件
        for i, xml_file in enumerate(xml_files):
            if not self.processing:
                break
            
            try:
                base_name = os.path.basename(xml_file)
                output_file = os.path.join(output_dir, base_name)
                
                self.log(f"处理文件 ({i+1}/{total_files}): {base_name}")
                success = self.process_single_xml(xml_file, output_file)
                
                if success:
                    self.log(f"成功处理并保存到: {output_file}")
                else:
                    self.log(f"处理文件失败: {base_name}")
                
            except Exception as e:
                self.log(f"处理 {os.path.basename(xml_file)} 时出错: {str(e)}")
            
            # 更新进度条
            self.progress['value'] = i + 1
            self.root.update_idletasks()
    
    def process_single_xml(self, input_file, output_file):
        # 解析XML文件
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()
        except Exception as e:
            self.log(f"解析XML错误: {str(e)}")
            return False
        
        # 提取标题
        title_text = self.extract_title(root)
        
        # 提取摘要
        abstract_text = self.extract_abstract(root)
        
        # 提取参考文献信息
        self.references = {}
        self.extract_bibliography(root)
        
        # 查找正文
        body = root.find(".//tei:body", self.xml_namespace)
        if body is None:
            self.log("找不到正文元素")
            return False
        
        # 处理正文中的引用
        processed_body = self.process_references_in_text(body)
        
        # 提取并组合div内容
        all_divs_content = ""
        for div in processed_body.findall("tei:div", self.xml_namespace):
            div_text = self.serialize_div(div)
            all_divs_content += div_text # 不需要额外的换行，serialize_div已处理
        
        # 如果选择了只使用ASCII编码，则转换内容
        if self.use_ascii_only_var.get():
            # 转换为ASCII并删除非ASCII字符
            self.log("正在转换为ASCII编码并删除非ASCII字符...")
            title_text = self.convert_to_ascii(title_text)
            abstract_text = self.convert_to_ascii(abstract_text)
            all_divs_content = self.convert_to_ascii(all_divs_content)
            xml_declaration = '<?xml version="1.0" encoding="ASCII"?>\n'
        else:
            xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        
        # 保存到输出文件，并添加根元素
        encoding = 'ascii' if self.use_ascii_only_var.get() else 'utf-8'
        with open(output_file, 'w', encoding=encoding) as f:
            f.write(xml_declaration) # 添加XML声明
            f.write('<document>\n') # 写入根元素开始标签
            
            # 写入标题
            if title_text:
                f.write(f'<title level="a" type="main">{title_text}</title>\n')
            
            # 写入摘要
            if abstract_text:
                f.write(f'<abstract>{abstract_text}</abstract>\n')
                
            # 写入正文内容
            f.write(all_divs_content)
            f.write('</document>\n') # 写入根元素结束标签
        
        return True
    
    def extract_title(self, root):
        """提取文档标题"""
        try:
            title_element = root.find(".//tei:fileDesc/tei:titleStmt/tei:title[@level='a'][@type='main']", self.xml_namespace)
            if title_element is not None and title_element.text:
                return title_element.text.strip()
        except Exception as e:
            self.log(f"提取标题时出错: {str(e)}")
        return ""
    
    def extract_abstract(self, root):
        """提取并处理摘要文本，去除type='figure'的内容"""
        try:
            abstract_div = root.find(".//tei:profileDesc/tei:abstract/tei:div", self.xml_namespace)
            if abstract_div is None:
                return ""
            
            abstract_text = ""
            for p in abstract_div.findall(".//tei:p", self.xml_namespace):
                # 处理段落内容，跳过带有type="figure"属性的内容
                para_text = ""
                
                # 处理段落中的所有子元素
                if p.text:
                    para_text += p.text
                
                for child in p:
                    # 跳过图表引用
                    if child.tag == f"{{{self.xml_namespace['tei']}}}ref" and child.get('type') == 'figure':
                        # 如果后面有文本，添加它
                        if child.tail:
                            para_text += child.tail
                        continue
                    
                    # 处理其他元素
                    child_text = self.get_element_text(child)
                    para_text += child_text
                    
                    # 添加尾部文本
                    if child.tail:
                        para_text += child.tail
                
                abstract_text += para_text + " "
            
            return abstract_text.strip()
        except Exception as e:
            self.log(f"提取摘要时出错: {str(e)}")
            return ""
    
    def extract_bibliography(self, root):
        """提取并格式化参考文献"""
        bib_structs = root.findall(".//tei:listBibl/tei:biblStruct", self.xml_namespace)
        
        for bib in bib_structs:
            ref_id = bib.get('{http://www.w3.org/XML/1998/namespace}id')
            
            # 提取作者
            author_elements = bib.findall(".//tei:author/tei:persName", self.xml_namespace)
            authors = []
            
            for author in author_elements:
                forename = author.find("tei:forename", self.xml_namespace)
                surname = author.find("tei:surname", self.xml_namespace)
                
                if forename is not None and surname is not None:
                    forename_text = forename.text if forename.text else ""
                    surname_text = surname.text if surname.text else ""
                    authors.append(f"{surname_text}, {forename_text}")
            
            # 提取标题
            title = bib.find(".//tei:title[@level='a']", self.xml_namespace)
            title_text = title.text if title is not None and title.text else ""
            
            # 提取期刊名称
            journal = bib.find(".//tei:title[@level='j']", self.xml_namespace)
            journal_text = journal.text if journal is not None and journal.text else ""
            
            # 提取年份
            year = bib.find(".//tei:date[@type='published']", self.xml_namespace)
            year_text = year.get('when') if year is not None and year.get('when') else ""
            
            # 提取卷号
            volume = bib.find(".//tei:biblScope[@unit='volume']", self.xml_namespace)
            volume_text = volume.text if volume is not None and volume.text else ""
            
            # 提取期号
            issue = bib.find(".//tei:biblScope[@unit='issue']", self.xml_namespace)
            issue_text = issue.text if issue is not None and issue.text else ""
            
            # 提取页码
            page = bib.find(".//tei:biblScope[@unit='page']", self.xml_namespace)
            page_text = ""
            if page is not None:
                if page.text:
                    page_text = page.text
                elif page.get('from') and page.get('to'):
                    page_text = f"{page.get('from')}-{page.get('to')}"
                    
            # 提取DOI
            doi = bib.find(".//tei:idno[@type='DOI']", self.xml_namespace)
            doi_text = doi.text if doi is not None and doi.text else ""
            
            # 构建格式化引用
            formatted_ref = ""
            if authors:
                formatted_ref += " and ".join(authors) + ". "
            if title_text:
                formatted_ref += f"{title_text}. "
            if journal_text:
                formatted_ref += f"{journal_text}. "
            if year_text:
                formatted_ref += f"{year_text};"
            if volume_text:
                formatted_ref += f"{volume_text}"
            if issue_text:
                formatted_ref += f"({issue_text})"
            if page_text:
                formatted_ref += f":{page_text}. "
            if doi_text:
                formatted_ref += f"doi:{doi_text}"
                
            # 如果选择了只使用ASCII编码，则在这里也转换引用文本
            if self.use_ascii_only_var.get():
                formatted_ref = self.convert_to_ascii(formatted_ref)
                
            self.references[ref_id] = formatted_ref.strip()
    
    def process_references_in_text(self, body_element):
        """替换文本中的引用标记为参考文献信息"""
        # 处理body中的所有div元素
        for div in body_element.findall(".//tei:div", self.xml_namespace):
            div_content = ET.tostring(div, encoding='unicode', method='xml')
            
            # 查找所有引用元素并替换
            ref_tags = div.findall(".//tei:ref[@type='bibr']", self.xml_namespace)
            
            for ref in ref_tags:
                target = ref.get('target')
                
                if target and target.startswith('#'):
                    ref_id = target[1:]  # 去掉#字符
                    if ref_id in self.references:
                        # 创建带有格式化引用的新元素
                        ref.text = ""
                        for child in list(ref):
                            ref.remove(child)
                        ref.text = self.references[ref_id]
        
        return body_element
    
    def serialize_div(self, div):
        """将div元素转换为文本，同时保留段落标记"""
        div_text = ""
        
        # 处理标题（如果存在）
        head = div.find("tei:head", self.xml_namespace)
        if head is not None and head.text:
            head_text = head.text
            if self.use_ascii_only_var.get():
                head_text = self.convert_to_ascii(head_text)
            div_text += f"<h1>{head_text}</h1>\n"
        
        # 处理段落
        for p in div.findall("tei:p", self.xml_namespace):
            div_text += "<p>"
            
            # 处理所有文本和嵌套元素
            p_text = self.get_element_text(p)
            if self.use_ascii_only_var.get():
                p_text = self.convert_to_ascii(p_text)
            div_text += p_text
            
            div_text += "</p>\n"
        
        return div_text
    
    def get_element_text(self, element):
        """获取元素的文本内容，包括嵌套元素"""
        text = element.text or ""
        
        for child in element:
            # 特殊处理引用标记
            if child.tag == f"{{{self.xml_namespace['tei']}}}ref" and child.get('type') == 'bibr':
                target = child.get('target')
                if target and target.startswith('#'):
                    ref_id = target[1:]
                    if ref_id in self.references:
                        text += f"<ref>{self.references[ref_id]}</ref>"
                    else:
                        # 如果未找到引用，使用原始文本
                        child_text = child.text or ""
                        text += f"<ref>{child_text}</ref>"
                else:
                    child_text = child.text or ""
                    text += f"<ref>{child_text}</ref>"
            else:
                # 对于其他元素，递归获取文本
                text += self.get_element_text(child)
            
            # 添加尾部文本（如果有）
            if child.tail:
                text += child.tail
        
        return text

def fix_file_dialog():
    """修复Windows上的文件对话框问题"""
    try:
        # Windows平台特定修复
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

if __name__ == "__main__":
    fix_file_dialog()  # 尝试修复文件对话框问题
    root = tk.Tk()
    app = GrobidBatchProcessor(root)
    root.mainloop() 