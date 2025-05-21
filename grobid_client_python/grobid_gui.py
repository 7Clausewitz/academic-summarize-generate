import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import os
from tkinter import messagebox

class GrobidCommandGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("GROBID 命令生成器")
        self.root.geometry("1000x800")
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Service selection
        self.create_service_section()
        
        # Input/Output paths
        self.create_path_section()
        
        # Output format selection
        self.create_output_format_section()
        
        # Parameters
        self.create_parameters_section()
        
        # Command preview
        self.create_command_preview()
        
        # Generate button
        self.create_generate_button()

    def create_service_section(self):
        # Service selection frame
        service_frame = ttk.LabelFrame(self.main_frame, text="服务选择", padding="5")
        service_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Service options
        self.services = {
            "processFulltextDocument": "处理完整PDF文档",
            "processHeaderDocument": "仅处理文档头部",
            "processReferences": "处理参考文献",
            "processCitationList": "处理引用列表（txt文件）",
            "processCitationPatentST36": "处理ST36格式专利",
            "processCitationPatentPDF": "处理PDF格式专利"
        }
        
        self.service_var = tk.StringVar(value="processFulltextDocument")
        for i, (service, desc) in enumerate(self.services.items()):
            ttk.Radiobutton(service_frame, text=f"{service}\n{desc}", 
                           variable=self.service_var, value=service).grid(
                           row=i, column=0, sticky=tk.W, pady=2)

    def create_path_section(self):
        # Path frame
        path_frame = ttk.LabelFrame(self.main_frame, text="路径设置", padding="5")
        path_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Input path
        ttk.Label(path_frame, text="输入路径:").grid(row=0, column=0, sticky=tk.W)
        self.input_path = ttk.Entry(path_frame, width=50)
        self.input_path.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(path_frame, text="浏览", command=self.browse_input).grid(row=0, column=2)
        
        # Output path
        ttk.Label(path_frame, text="输出路径:").grid(row=1, column=0, sticky=tk.W)
        self.output_path = ttk.Entry(path_frame, width=50)
        self.output_path.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(path_frame, text="浏览", command=self.browse_output).grid(row=1, column=2)

    def create_output_format_section(self):
        # Output format frame
        format_frame = ttk.LabelFrame(self.main_frame, text="输出格式", padding="5")
        format_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.output_format = tk.StringVar(value="xml")
        ttk.Radiobutton(format_frame, text="XML格式 (TEI)", 
                       variable=self.output_format, value="xml").grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(format_frame, text="JSON格式", 
                       variable=self.output_format, value="json").grid(row=0, column=1, sticky=tk.W)

    def create_parameters_section(self):
        # Parameters frame
        param_frame = ttk.LabelFrame(self.main_frame, text="参数设置", padding="5")
        param_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Parameters with descriptions
        self.parameters = {
            "n": ("并发数", "并发处理数量（默认：10）"),
            "generateIDs": ("生成ID", "为XML元素生成随机ID"),
            "consolidate_header": ("合并头部", "合并文档头部元数据"),
            "consolidate_citations": ("合并引用", "合并引用元数据"),
            "include_raw_citations": ("包含原始引用", "包含原始引用字符串"),
            "include_raw_affiliations": ("包含原始单位", "包含原始单位信息"),
            "force": ("强制处理", "强制重新处理已存在的文件"),
            "teiCoordinates": ("TEI坐标", "在输出中添加PDF坐标信息"),
            "segmentSentences": ("句子分割", "添加句子分割标记"),
            "verbose": ("详细输出", "显示详细的处理信息")
        }
        
        # Create checkboxes and entries for parameters
        self.param_vars = {}
        for i, (param, (label, desc)) in enumerate(self.parameters.items()):
            if param == "n":
                ttk.Label(param_frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W)
                self.param_vars[param] = ttk.Entry(param_frame, width=10)
                self.param_vars[param].insert(0, "10")
                self.param_vars[param].grid(row=i, column=1, sticky=tk.W)
                ttk.Label(param_frame, text=desc).grid(row=i, column=2, sticky=tk.W)
            else:
                self.param_vars[param] = tk.BooleanVar()
                ttk.Checkbutton(param_frame, text=label, variable=self.param_vars[param]).grid(
                    row=i, column=0, sticky=tk.W)
                ttk.Label(param_frame, text=desc).grid(row=i, column=1, columnspan=2, sticky=tk.W)

    def create_command_preview(self):
        # Command preview frame
        preview_frame = ttk.LabelFrame(self.main_frame, text="命令预览", padding="5")
        preview_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.command_preview = scrolledtext.ScrolledText(preview_frame, height=5, width=80)
        self.command_preview.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Copy button
        ttk.Button(preview_frame, text="复制命令", 
                  command=self.copy_command).grid(row=1, column=0, pady=5)

    def create_generate_button(self):
        ttk.Button(self.main_frame, text="生成命令", 
                  command=self.generate_command).grid(row=5, column=0, columnspan=2, pady=10)

    def browse_input(self):
        path = tk.filedialog.askdirectory()
        if path:
            self.input_path.delete(0, tk.END)
            self.input_path.insert(0, path)

    def browse_output(self):
        path = tk.filedialog.askdirectory()
        if path:
            self.output_path.delete(0, tk.END)
            self.output_path.insert(0, path)

    def generate_command(self):
        # Build command
        cmd = ["grobid_client"]
        
        # Add input path
        input_path = self.input_path.get()
        if input_path:
            cmd.extend(["--input", f'"{input_path}"'])
        
        # Add output path
        output_path = self.output_path.get()
        if output_path:
            cmd.extend(["--output", f'"{output_path}"'])
        
        # Add parameters
        for param, var in self.param_vars.items():
            if param == "n":
                if var.get():
                    cmd.extend(["--n", var.get()])
            elif var.get():
                cmd.append(f"--{param}")
        
        # Add output format
        if self.output_format.get() == "json":
            cmd.append("--json")
        
        # Add service
        cmd.append(self.service_var.get())
        
        # Update preview
        self.command_preview.delete(1.0, tk.END)
        self.command_preview.insert(tk.END, " ".join(cmd))

    def copy_command(self):
        command = self.command_preview.get(1.0, tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        messagebox.showinfo("成功", "命令已复制到剪贴板！")

if __name__ == "__main__":
    root = tk.Tk()
    app = GrobidCommandGenerator(root)
    root.mainloop() 