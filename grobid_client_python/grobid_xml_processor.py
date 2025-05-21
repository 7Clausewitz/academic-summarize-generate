import xml.etree.ElementTree as ET
import re
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, Frame, Button, Label, Text, Scrollbar
import os

class GrobidXMLProcessor:
    def __init__(self):
        self.xml_namespace = {'tei': 'http://www.tei-c.org/ns/1.0'}
        self.references = {}  # Will store reference ID to formatted citation mapping
        
    def parse_xml(self, xml_file):
        """Parse the XML file"""
        try:
            tree = ET.parse(xml_file)
            return tree.getroot()
        except Exception as e:
            print(f"解析XML错误: {e}")
            return None

    def extract_bibliography(self, root):
        """Extract and format bibliographic references"""
        bib_structs = root.findall(".//tei:listBibl/tei:biblStruct", self.xml_namespace)
        
        for bib in bib_structs:
            ref_id = bib.get('{http://www.w3.org/XML/1998/namespace}id')
            
            # Extract authors
            author_elements = bib.findall(".//tei:author/tei:persName", self.xml_namespace)
            authors = []
            
            for author in author_elements:
                forename = author.find("tei:forename", self.xml_namespace)
                surname = author.find("tei:surname", self.xml_namespace)
                
                if forename is not None and surname is not None:
                    forename_text = forename.text if forename.text else ""
                    surname_text = surname.text if surname.text else ""
                    authors.append(f"{surname_text}, {forename_text}")
            
            # Extract title
            title = bib.find(".//tei:title[@level='a']", self.xml_namespace)
            title_text = title.text if title is not None and title.text else ""
            
            # Extract journal name
            journal = bib.find(".//tei:title[@level='j']", self.xml_namespace)
            journal_text = journal.text if journal is not None and journal.text else ""
            
            # Extract year
            year = bib.find(".//tei:date[@type='published']", self.xml_namespace)
            year_text = year.get('when') if year is not None and year.get('when') else ""
            
            # Extract volume
            volume = bib.find(".//tei:biblScope[@unit='volume']", self.xml_namespace)
            volume_text = volume.text if volume is not None and volume.text else ""
            
            # Extract issue
            issue = bib.find(".//tei:biblScope[@unit='issue']", self.xml_namespace)
            issue_text = issue.text if issue is not None and issue.text else ""
            
            # Extract pages
            page = bib.find(".//tei:biblScope[@unit='page']", self.xml_namespace)
            page_text = ""
            if page is not None:
                if page.text:
                    page_text = page.text
                elif page.get('from') and page.get('to'):
                    page_text = f"{page.get('from')}-{page.get('to')}"
                    
            # Extract DOI
            doi = bib.find(".//tei:idno[@type='DOI']", self.xml_namespace)
            doi_text = doi.text if doi is not None and doi.text else ""
            
            # Construct formatted reference
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
                
            self.references[ref_id] = formatted_ref.strip()

    def process_references_in_text(self, body_element):
        """Replace reference tags with their bibliographic information"""
        # Process all div elements in the body
        for div in body_element.findall(".//tei:div", self.xml_namespace):
            div_content = ET.tostring(div, encoding='unicode', method='xml')
            
            # Find all reference elements and replace them
            ref_tags = div.findall(".//tei:ref[@type='bibr']", self.xml_namespace)
            
            for ref in ref_tags:
                target = ref.get('target')
                
                if target and target.startswith('#'):
                    ref_id = target[1:]  # Remove the # character
                    if ref_id in self.references:
                        # Create a new element with the formatted reference
                        ref.text = ""
                        for child in list(ref):
                            ref.remove(child)
                        ref.text = self.references[ref_id]
        
        return body_element

    def process_file(self, input_file, output_file):
        """Process the XML file and save the output"""
        root = self.parse_xml(input_file)
        if root is None:
            return False
            
        # Extract bibliography
        self.extract_bibliography(root)
        
        # Find the body element
        body = root.find(".//tei:body", self.xml_namespace)
        if body is None:
            print("找不到正文元素")
            return False
            
        # Process references in the body text
        processed_body = self.process_references_in_text(body)
        
        # Extract and save only the div content from the body
        output_text = ""
        for div in processed_body.findall("tei:div", self.xml_namespace):
            div_text = self.serialize_div(div)
            output_text += div_text + "\n\n"
        
        # Write to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_text)
        
        return True
    
    def serialize_div(self, div):
        """Convert a div element to text while preserving paragraph tags"""
        div_text = ""
        
        # Process the heading if it exists
        head = div.find("tei:head", self.xml_namespace)
        if head is not None and head.text:
            div_text += f"<h1>{head.text}</h1>\n"
        
        # Process paragraphs
        for p in div.findall("tei:p", self.xml_namespace):
            # 检查是否有句子标记
            s_elements = p.findall(".//tei:s", self.xml_namespace)
            
            if s_elements:
                # 如果有句子标记，按照字符数量限制处理
                current_p_text = "<p>"
                current_length = 0
                
                for s in s_elements:
                    s_text = self.get_element_text(s)
                    s_with_tags = f"<s>{s_text}</s>"
                    s_length = len(s_text)
                    
                    # 如果当前段落已经超过5000字符，且这是超过后的第一个句子，则结束当前段落，开始新段落
                    if current_length > 5000:
                        current_p_text += "</p>\n"
                        div_text += current_p_text
                        current_p_text = "<p>"
                        current_length = 0
                    
                    # 将句子添加到当前段落
                    current_p_text += s_with_tags
                    current_length += s_length
                
                # 添加最后一个段落的结束标记
                if current_p_text != "<p>":
                    current_p_text += "</p>\n"
                    div_text += current_p_text
            else:
                # 如果没有句子标记，则尝试手动分割长段落
                p_text = self.get_element_text(p)
                
                # 如果段落长度小于5000，直接输出
                if len(p_text) <= 5000:
                    div_text += f"<p>{p_text}</p>\n"
                else:
                    # 分割长段落
                    segments = self.split_long_paragraph(p_text)
                    for segment in segments:
                        div_text += f"<p>{segment}</p>\n"
        
        return div_text
    
    def split_long_paragraph(self, text, max_length=5000):
        """将长段落按照最大长度分割成多个段落，尽量在句号、问号、感叹号等处分割"""
        segments = []
        start = 0
        
        while start < len(text):
            # 如果剩余文本不足max_length，直接作为一个段落
            if start + max_length >= len(text):
                segments.append(text[start:])
                break
            
            # 在max_length之后寻找第一个合适的分割点（句号、问号、感叹号后加空格）
            end = start + max_length
            
            # 寻找句号、问号、感叹号等后跟空格的位置
            split_positions = []
            for pattern in ['. ', '? ', '! ', '。', '？', '！']:
                pos = text.find(pattern, end)
                if pos != -1:
                    if pattern in ['. ', '? ', '! ']:
                        split_positions.append(pos + 2)  # 包括标点和空格
                    else:
                        split_positions.append(pos + 1)  # 中文标点
            
            # 找不到合适的分割点时，在空格处分割
            if not split_positions:
                # 向后查找最近的空格
                pos = text.find(' ', end)
                if pos != -1:
                    split_positions.append(pos + 1)
            
            # 找不到任何分割点时，强制分割
            if not split_positions:
                segments.append(text[start:end])
                start = end
            else:
                # 使用最近的分割点
                nearest_pos = min(split_positions)
                segments.append(text[start:nearest_pos])
                start = nearest_pos
        
        return segments
    
    def get_element_text(self, element):
        """Get text content from an element, including nested elements"""
        text = element.text or ""
        
        for child in element:
            # Special handling for reference tags
            if child.tag == f"{{{self.xml_namespace['tei']}}}ref" and child.get('type') == 'bibr':
                target = child.get('target')
                if target and target.startswith('#'):
                    ref_id = target[1:]
                    if ref_id in self.references:
                        text += f"<ref>{self.references[ref_id]}</ref>"
                    else:
                        # Use original text of the reference if not found
                        child_text = child.text or ""
                        text += f"<ref>{child_text}</ref>"
                else:
                    child_text = child.text or ""
                    text += f"<ref>{child_text}</ref>"
            # 特殊处理句子标记
            elif child.tag == f"{{{self.xml_namespace['tei']}}}s":
                # 对于嵌套在其他元素内的句子标记，也要保留
                s_text = self.get_element_text(child)
                text += f"<s>{s_text}</s>"
            else:
                # For other elements, recursively get their text
                text += self.get_element_text(child)
            
            # Add tail text if any
            if child.tail:
                text += child.tail
        
        return text

class GrobidXMLProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("GROBID XML 处理工具")
        self.root.geometry("800x600")
        
        self.processor = GrobidXMLProcessor()
        
        # Create frames
        self.top_frame = Frame(root)
        self.top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.middle_frame = Frame(root)
        self.middle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.bottom_frame = Frame(root)
        self.bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Top frame - file selection buttons
        self.input_label = Label(self.top_frame, text="未选择文件", width=40)
        self.input_label.pack(side=tk.LEFT, padx=5)
        
        self.select_button = Button(self.top_frame, text="选择XML文件", command=self.select_file)
        self.select_button.pack(side=tk.LEFT, padx=5)
        
        self.process_button = Button(self.top_frame, text="处理文件", command=self.process_file)
        self.process_button.pack(side=tk.LEFT, padx=5)
        
        # Middle frame - text display area
        self.text_display = scrolledtext.ScrolledText(self.middle_frame, wrap=tk.WORD)
        self.text_display.pack(fill=tk.BOTH, expand=True)
        
        # Bottom frame - status and save button
        self.status_label = Label(self.bottom_frame, text="就绪", width=40)
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.save_button = Button(self.bottom_frame, text="保存结果", command=self.save_output)
        self.save_button.pack(side=tk.RIGHT, padx=5)
        
        # Initialize variables
        self.input_file = None
        self.output_text = ""
    
    def select_file(self):
        """Open file dialog to select an XML file"""
        file_path = filedialog.askopenfilename(
            title="选择GROBID XML文件",
            filetypes=[("XML文件", "*.xml"), ("所有文件", "*.*")],
            initialdir=os.getcwd()  # 设置初始目录为当前工作目录
        )
        
        if file_path:
            self.input_file = file_path
            self.input_label.config(text=os.path.basename(file_path))
            self.status_label.config(text="已选择文件，可以开始处理。")
            print(f"已选择文件: {file_path}")  # 添加调试输出
    
    def process_file(self):
        """Process the selected XML file"""
        if not self.input_file:
            messagebox.showerror("错误", "请先选择XML文件。")
            return
        
        self.status_label.config(text="处理中...")
        self.root.update()
        
        # Create a temporary output file
        temp_output = f"{self.input_file}.processed.txt"
        
        # Process the file
        success = self.processor.process_file(self.input_file, temp_output)
        
        if success:
            # Read the processed output
            with open(temp_output, 'r', encoding='utf-8') as f:
                self.output_text = f.read()
            
            # Display in text area
            self.text_display.delete(1.0, tk.END)
            self.text_display.insert(tk.END, self.output_text)
            
            self.status_label.config(text="处理完成，可以保存结果。")
            
            # Clean up temp file
            os.remove(temp_output)
        else:
            self.status_label.config(text="处理文件时出错。")
            messagebox.showerror("错误", "处理XML文件失败。")
    
    def save_output(self):
        """Save the processed output to a file"""
        if not self.output_text:
            messagebox.showerror("错误", "没有处理结果可以保存。")
            return
        
        output_file = filedialog.asksaveasfilename(
            title="保存处理结果",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialdir=os.getcwd()  # 设置初始目录为当前工作目录
        )
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(self.output_text)
            
            self.status_label.config(text=f"已保存到 {os.path.basename(output_file)}")
            messagebox.showinfo("成功", f"结果已保存到 {output_file}")

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
    app = GrobidXMLProcessorGUI(root)
    root.mainloop() 