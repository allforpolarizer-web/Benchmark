"""
根据评测规则，通过llm.py调用gemini api对结构分析助手的迭代编程表现进行评测
"""
# -*- coding: utf-8 -*-
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import GeminiClient
from typing import Optional, Dict, Tuple
import json


class PostProcessor:
    """生成评测报告"""
    
    # 中英文映射
    INTENTION_MAP = {
        "静力分析": "statics",
        "模态分析": "modal",
        "地震谱分析": "spectrum",
        "时程分析": "timehistory"
    }
    
    STRUCTURE_MAP = {
        "框架": "frame",
        "框架结构": "frame",
        "剪力墙": "wall",
        "剪力墙结构": "wall",
        "框架剪力墙": "frame-wall",
        "框架剪力墙结构": "frame-wall"
    }
    
    def __init__(self, api_key: Optional[str] = None, output_dir: str = "output"):
        self.client = GeminiClient(api_key=api_key)
        self.output_dir = output_dir
        self.report_dir = os.path.join(output_dir, "report")
        os.makedirs(self.report_dir, exist_ok=True)
    
    def _translate_to_english(self, structure: str, intention: str) -> Tuple[str, str]:
        """将中文结构类型和意图类型转换为英文"""
        structure_key = structure.strip()
        if structure_key.endswith("结构") and structure_key not in self.STRUCTURE_MAP:
            structure_key = structure_key[:-2]
        structure_en = self.STRUCTURE_MAP.get(structure_key, structure_key.lower().replace(" ", "-"))

        intention_key = intention.strip()
        intention_en = self.INTENTION_MAP.get(intention_key, intention_key.lower().replace(" ", "-"))
        return structure_en, intention_en
    
    def evaluate(self, inference_result: Dict) -> str:
        """
        评测推理结果并生成报告
        
        Args:
            inference_result: inference.py返回的结果字典
        
        Returns:
            报告文件路径
        """
        structure = inference_result["structure"]
        intention = inference_result["intention"]
        prompt = inference_result["prompt"]
        iterations = inference_result["iterations"]
        final_success = inference_result["final_success"]
        run_index = inference_result.get("run_index", 1)
        
        # 构建评测prompt
        evaluation_prompt = f"""请对结构分析助手的迭代编程表现进行评测。

用户需求：{prompt}
结构类型：{structure}
分析类型：{intention}
评测轮次：第{run_index}次

迭代过程：
"""
        
        for iter_info in iterations:
            evaluation_prompt += f"""
迭代 {iter_info['iteration']}:
- 文件路径: {iter_info.get('filepath', 'N/A')}
- 是否成功: {'是' if iter_info.get('success') else '否'}
"""
            if iter_info.get('error_info'):
                evaluation_prompt += f"- 错误信息: {iter_info['error_info']}\n"
            if iter_info.get('stdout'):
                evaluation_prompt += f"- 标准输出: {iter_info['stdout'][:500]}...\n"
        
        evaluation_prompt += f"""
最终结果: {'成功' if final_success else '失败'}
总迭代次数: {len(iterations)}

请生成一份详细的评测报告，包括：
1. 任务完成情况评估
2. 代码质量分析
3. 迭代过程分析
4. 错误处理能力评估
5. 改进建议
6. 综合评分（0-100分）

报告使用Markdown格式，标题清晰，内容详细："""

        report_content = self.client.call(evaluation_prompt)
        
        if not report_content:
            # 如果LLM生成失败，生成基础报告
            report_content = self._generate_basic_report(inference_result)
        
        # 保存报告（使用英文名称）
        structure_en, intention_en = self._translate_to_english(structure, intention)
        report_name = f"{structure_en}-{intention_en}-{run_index}.md"
        report_path = os.path.join(self.report_dir, report_name)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# 结构分析助手评测报告\n\n")
            f.write(f"**结构类型**: {structure}\n\n")
            f.write(f"**分析类型**: {intention}\n\n")
            f.write(f"**用户需求**: {prompt}\n\n")
            f.write(f"**最终结果**: {'✅ 成功' if final_success else '❌ 失败'}\n\n")
            f.write(f"**评测轮次**: 第 {run_index} 次\n\n")
            f.write(f"**总迭代次数**: {len(iterations)}\n\n")
            f.write("---\n\n")
            f.write(report_content)
        
        print(f"\n{'='*60}")
        print(f"评测报告已生成: {report_path}")
        print(f"{'='*60}\n")
        
        return report_path
    
    def _generate_basic_report(self, inference_result: Dict) -> str:
        """生成基础报告（当LLM生成失败时使用）"""
        structure = inference_result["structure"]
        intention = inference_result["intention"]
        iterations = inference_result["iterations"]
        final_success = inference_result["final_success"]
        run_index = inference_result.get("run_index", 1)
        
        report = f"""## 评测结果

### 任务完成情况
- **最终状态**: {'成功' if final_success else '失败'}
- **迭代次数**: {len(iterations)}
- **评测轮次**: 第 {run_index} 次

### 迭代过程
"""
        
        for iter_info in iterations:
            report += f"""
#### 迭代 {iter_info['iteration']}
- **状态**: {'成功' if iter_info.get('success') else '失败'}
- **文件**: {iter_info.get('filepath', 'N/A')}
"""
            if iter_info.get('error_info'):
                report += f"- **错误**: {iter_info['error_info']}\n"
        
        report += f"""
### 综合评分
- **完成度**: {100 if final_success else len(iterations) * 10}分
- **迭代效率**: {100 // len(iterations) if iterations else 0}分
"""
        
        return report

