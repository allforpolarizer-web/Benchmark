"""
根据sampler.py选择的用户意图和结构类型，通过llm.py调用gemini api扮演用户生成相应类别的一个prompt
"""
# -*- coding: utf-8 -*-
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import GeminiClient
from typing import Optional


class PromptGenerator:
    """生成用户prompt"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = GeminiClient(api_key=api_key)
    
    def generate(self, intention: str, structure: str) -> str:
        """
        根据用户意图和结构类型生成prompt
        
        Args:
            intention: 用户意图（如：静力分析、模态分析等）
            structure: 结构类型（如：框架、剪力墙等）
        
        Returns:
            生成的prompt字符串
        """
        system_prompt = f"""你是一个需要结构分析的用户。请根据以下信息生成一个具体的结构分析需求prompt：

用户意图：{intention}
结构类型：{structure}

请生成一个自然、具体的用户需求描述，要求：
1. 语言自然，像真实用户提出的问题
2. 包含具体的结构分析需求
3. 描述清晰，包含必要的参数信息（如材料属性、几何尺寸、荷载等）
4. 只输出用户需求描述，不要包含其他解释

用户需求："""

        prompt = self.client.call(system_prompt)
        
        if prompt:
            print(f"\n{'='*60}")
            print("生成的用户Prompt:")
            print(f"{'='*60}")
            print(prompt)
            print(f"{'='*60}\n")
            return prompt
        else:
            raise RuntimeError("生成prompt失败")

