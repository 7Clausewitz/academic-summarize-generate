import os

from volcenginesdkarkruntime import Ark


client = Ark(api_key="9a46f5a5-7ce1-4aa3-961e-0c90b0c23c60")

prompt = f"""
你的任务是根据提供的一小节大纲和搜索的文献的摘要信息，思考大纲书写应当包含的内容，找出对于文章的逻辑至关重要的信息以及重要的专业术语信息，最后输出最想检索的关键字，以json格式呈现。

首先，请仔细阅读以下一小节大纲：
介绍非介入栓塞疗法的定义及临床意义，阐述多模态联合疗法的协同效应、减少副作用、提高疗效等优势，并说明综述的目的与结构。

接着，请仔细阅读以下搜索的文献的摘要信息：
<abstract>Figure 3.In vitro targeting and toxicity of Th-TPZ@MOF-FA.A) CLSM images and 3D confocal fluorescence images and B) flow cytometry analyses of HepG2 cells incubated with Th-TPZ@MOF-PEG (30 mg L -1 ) and Th-TPZ@MOF-FA (30 mg L -1 ) for 4 h: nuclei stained with Hoechst 33342 (Hoechst, blue signal) and nanocarriers labeled by FAM (green signal).Scale bars: 10 m.C) Calcein AM/propidium iodide (PI) staining of HepG2 cells treated with Th-TPZ@MOF-FA (50 mg L -1 ) at different conditions (pH 7.4 and 6.5) under normoxia and hypoxia.Calcein AM: green signal, PI: red signal.Scale bars: 50 m.D) Cell viability of Th-TPZ@MOF-FA at pH 7.4 and 6.5 under normoxic and hypoxic conditions.E) Fluorescein-annexin V and PI staining assays of HepG2 cells treated with different formulations at pH 7.4 and 6.5 under</abstract>


在思考大纲书写应包含的内容时，需结合大纲和文献摘要，分析大纲所涉及主题的核心要素、关联要点等。
对于确定对文章逻辑至关重要的信息，要考虑哪些信息是构建文章逻辑框架必不可少的；确定重要专业术语信息时，需找出在大纲和文献摘要中具有专业含义且对理解主题有重要作用的词汇。

以json格式输出你最想检索的关键词，最多不超过10个关键词。
{{
  "keywords": []
}}
"""

completion = client.chat.completions.create(
                    model="doubao-1-5-thinking-pro-250415",
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": "{"},
                    ]
                )
                
response = completion.choices[0].message.content
import re
response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)

print(response)