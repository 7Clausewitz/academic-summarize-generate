import os
import subprocess
import xml.etree.ElementTree as ET
import glob
import threading
import time
import sys

class GrobidProcessor:
    def __init__(self, logger=None):
        """
        初始化GROBID处理器
        
        参数:
            logger: 可选的记录器函数，用于输出日志信息
        """
        # 创建命名空间变量
        self.xml_namespace = {'tei': 'http://www.tei-c.org/ns/1.0'}
        self.references = {}  # 存储参考文献ID到格式化引用的映射
        
        # 处理状态
        self.processing = False
        
        # 日志函数
        self.logger = logger if logger else print
        
        # 段落长度阈值，小于此值的段落将被删除
        self.min_paragraph_length = 150
        
    def log(self, message):
        """输出日志"""
        self.logger(message)
    
    def process_batch(self, input_path, output_path, final_output_path, 
                      grobid_client="grobid_client", concurrency=300,
                      include_raw_citations=True, segment_sentences=True,
                      use_ascii_only=True, min_paragraph_length=150):
        """
        批量处理PDF文件
        
        参数:
            input_path: PDF输入文件夹路径
            output_path: XML输出文件夹路径
            final_output_path: 最终处理结果输出文件夹路径
            grobid_client: GROBID客户端路径
            concurrency: 并发数
            include_raw_citations: 是否保留原始引用
            segment_sentences: 是否进行句子分割
            use_ascii_only: 是否只使用ASCII字符(删除非ASCII字符)
            min_paragraph_length: 段落最小长度阈值，小于此值的段落将被删除
            
        返回:
            bool: 处理是否成功
        """
        # 验证路径
        if not input_path or not os.path.isdir(input_path):
            self.log("错误：请提供有效的PDF输入文件夹")
            return False
        
        if not output_path:
            self.log("错误：请提供XML输出文件夹")
            return False
        
        if not final_output_path:
            self.log("错误：请提供处理后文件输出文件夹")
            return False
        
        # 创建输出目录（如果不存在）
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(final_output_path, exist_ok=True)
        
        # 设置处理参数
        self.grobid_client = grobid_client
        self.concurrency = concurrency
        self.include_raw_citations = include_raw_citations
        self.segment_sentences = segment_sentences
        self.use_ascii_only = use_ascii_only
        self.min_paragraph_length = min_paragraph_length
        
        # 设置处理状态
        self.processing = True
        
        try:
            # 第一步：使用GROBID处理PDF文件
            self.log("=== 步骤1：使用GROBID处理PDF文件 ===")
            self.run_grobid_processing(input_path, output_path)
            
            if not self.processing:
                self.log("处理已停止")
                return False
            
            # 第二步：处理生成的XML文件
            self.log("\n=== 步骤2：处理生成的XML文件 ===")
            self.process_xml_files(output_path, final_output_path)
            
            self.log("\n处理完成！")
            return True
        except Exception as e:
            self.log(f"处理过程中出错: {str(e)}")
            return False
        finally:
            self.processing = False
    
    def stop_processing(self):
        """停止处理"""
        if self.processing:
            self.processing = False
            self.log("正在停止处理...")
    
    def run_grobid_processing(self, input_path, output_path):
        """
        运行GROBID处理PDF文件
        
        参数:
            input_path: PDF输入文件夹路径
            output_path: XML输出文件夹路径
        """
        # 构建命令
        cmd = [
            self.grobid_client,
            "--input", input_path,
            "--output", output_path,
            "--n", str(self.concurrency)
        ]
        
        # 添加选项
        if self.include_raw_citations:
            cmd.append("--include_raw_citations")
        
        if self.segment_sentences:
            cmd.append("--segmentSentences")
        
        # 添加service参数（必需）
        cmd.append("processFulltextDocument")
        
        self.log(f"执行命令: {' '.join(cmd)}")
        
        # 确定 grobid_client_python 目录作为工作目录
        # 假设 config.json 位于与 grobid_processor.py 相同的目录
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
        """
        处理生成的XML文件
        
        参数:
            xml_dir: XML文件夹路径
            output_dir: 输出文件夹路径
        """
        # 获取所有XML文件
        xml_files = glob.glob(os.path.join(xml_dir, "*.xml"))
        total_files = len(xml_files)
        
        if total_files == 0:
            self.log("没有找到XML文件进行处理")
            return
        
        self.log(f"找到 {total_files} 个XML文件需要处理")
        
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
    
    def process_single_xml(self, input_file, output_file):
        """
        处理单个XML文件
        
        参数:
            input_file: 输入XML文件路径
            output_file: 输出文件路径
            
        返回:
            bool: 处理是否成功
        """
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
        if self.use_ascii_only:
            # 转换为ASCII并删除非ASCII字符
            self.log("正在转换为ASCII编码并删除非ASCII字符...")
            title_text = self.convert_to_ascii(title_text)
            abstract_text = self.convert_to_ascii(abstract_text)
            all_divs_content = self.convert_to_ascii(all_divs_content)
            xml_declaration = '<?xml version="1.0" encoding="ASCII"?>\n'
        else:
            xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        
        # 保存到输出文件，并添加根元素
        encoding = 'ascii' if self.use_ascii_only else 'utf-8'
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
            if self.use_ascii_only:
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
            if self.use_ascii_only:
                head_text = self.convert_to_ascii(head_text)
            div_text += f"<h1>{head_text}</h1>\n"
        
        # 处理段落
        for p in div.findall("tei:p", self.xml_namespace):
            # 处理所有文本和嵌套元素
            p_text = self.get_element_text(p)
            if self.use_ascii_only:
                p_text = self.convert_to_ascii(p_text)
            
            # 判断段落长度，小于阈值的段落将被删除
            if len(p_text) >= self.min_paragraph_length:
                div_text += f"<p>{p_text}</p>\n"
            else:
                self.log(f"删除了长度为 {len(p_text)} 的短段落 (阈值: {self.min_paragraph_length})")
        
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

# 示例用法
if __name__ == "__main__":
    # 参数解析
    import argparse
    
    parser = argparse.ArgumentParser(description='GROBID PDF处理工具')
    parser.add_argument('--input', required=True, help='PDF输入文件夹路径')
    parser.add_argument('--output', required=True, help='XML输出文件夹路径')
    parser.add_argument('--final_output', required=True, help='最终处理结果输出文件夹路径')
    parser.add_argument('--grobid_client', default='grobid_client', help='GROBID客户端路径')
    parser.add_argument('--concurrency', type=int, default=300, help='并发数')
    parser.add_argument('--no_raw_citations', action='store_false', dest='include_raw_citations', help='不保留原始引用')
    parser.add_argument('--no_segment_sentences', action='store_false', dest='segment_sentences', help='不进行句子分割')
    parser.add_argument('--no_ascii_only', action='store_false', dest='use_ascii_only', help='使用UTF-8而非ASCII')
    parser.add_argument('--min_paragraph_length', type=int, default=150, help='段落最小长度阈值，小于此值的段落将被删除')
    
    args = parser.parse_args()
    
    # 创建处理器并处理文件
    processor = GrobidProcessor()
    success = processor.process_batch(
        input_path=args.input,
        output_path=args.output,
        final_output_path=args.final_output,
        grobid_client=args.grobid_client,
        concurrency=args.concurrency,
        include_raw_citations=args.include_raw_citations,
        segment_sentences=args.segment_sentences,
        use_ascii_only=args.use_ascii_only,
        min_paragraph_length=args.min_paragraph_length
    )
    
    sys.exit(0 if success else 1) 