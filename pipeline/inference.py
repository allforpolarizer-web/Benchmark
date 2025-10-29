#!/usr/bin/env python3
"""
inference.py - 调用llm.py将prompt和TCL结构描述发给Gemini API进行分析
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from llm import OpenSeesSingleTurnAgent


def _safe_print(msg: str):
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore'))
        except Exception:
            pass


class StructureAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        """初始化结构分析器"""
        # 使用安全打印作为状态回调，避免Windows控制台编码错误导致崩溃
        self.agent = OpenSeesSingleTurnAgent(api_key=api_key, status_callback=_safe_print)
    
    def analyze_structure(self, prompt: str, tcl_content: str, 
                         temp_tcl_file: str = None) -> Dict[str, Any]:
        """
        分析结构
        
        Args:
            prompt: 用户prompt
            tcl_content: TCL结构描述内容
            temp_tcl_file: 临时TCL文件路径（如果为None，会自动创建）
        
        Returns:
            分析结果字典
        """
        # 如果没有提供临时文件路径，创建一个
        if temp_tcl_file is None:
            temp_tcl_file = self._create_temp_tcl_file(tcl_content)
        
        try:
            # 调用OpenSees Agent进行分析
            result = self.agent.process_single_turn(temp_tcl_file, prompt)
            
            # 添加额外信息
            result["prompt"] = prompt
            result["tcl_content"] = tcl_content
            result["temp_tcl_file"] = temp_tcl_file
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"分析过程中发生错误: {str(e)}",
                "prompt": prompt,
                "tcl_content": tcl_content,
                "temp_tcl_file": temp_tcl_file
            }
    
    def _create_temp_tcl_file(self, tcl_content: str) -> str:
        """创建临时TCL文件"""
        import tempfile
        import time
        
        # 创建临时文件
        timestamp = int(time.time())
        temp_dir = Path("temp_opensees")
        temp_dir.mkdir(exist_ok=True)
        
        temp_file = temp_dir / f"temp_structure_{timestamp}.tcl"
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(tcl_content)
        
        return str(temp_file)
    
    def analyze_with_custom_prompt(self, tcl_content: str, custom_prompt: str = None) -> Dict[str, Any]:
        """
        使用自定义prompt分析结构
        
        Args:
            tcl_content: TCL结构描述内容
            custom_prompt: 自定义分析prompt
        
        Returns:
            分析结果字典
        """
        if custom_prompt is None:
            custom_prompt = "请分析这个结构的内力、位移和模态特性"
        
        return self.analyze_structure(custom_prompt, tcl_content)
    
    def batch_analyze(self, analysis_tasks: list) -> list:
        """
        批量分析多个结构
        
        Args:
            analysis_tasks: 分析任务列表，每个任务包含prompt和tcl_content
        
        Returns:
            分析结果列表
        """
        results = []
        
        for i, task in enumerate(analysis_tasks):
            print(f"正在分析第 {i+1}/{len(analysis_tasks)} 个结构...")
            
            prompt = task.get("prompt", "结构分析")
            tcl_content = task.get("tcl_content", "")
            
            result = self.analyze_structure(prompt, tcl_content)
            results.append(result)
            
            # 添加任务索引
            result["task_index"] = i
        
        return results
    
    def get_analysis_summary(self, result: Dict[str, Any]) -> str:
        """获取分析结果摘要"""
        summary = []
        summary.append("=" * 50)
        summary.append("结构分析结果摘要")
        summary.append("=" * 50)
        
        summary.append(f"分析状态: {'成功' if result.get('success') else '失败'}")
        summary.append(f"用户prompt: {result.get('prompt', 'N/A')}")
        
        if result.get('think_response'):
            summary.append(f"思考过程: {result['think_response'][:200]}...")
        
        if result.get('execution_result'):
            exec_result = result['execution_result']
            summary.append(f"执行状态: {'成功' if exec_result.get('success') else '失败'}")
            if exec_result.get('stdout'):
                summary.append(f"输出: {exec_result['stdout'][:200]}...")
        
        if result.get('errors'):
            summary.append("错误信息:")
            for error in result['errors']:
                summary.append(f"  - {error}")
        
        summary.append("=" * 50)
        return "\n".join(summary)


def main():
    """测试函数"""
    print("=== 结构分析器测试 ===")
    
    try:
        analyzer = StructureAnalyzer()
        
        # 测试用的简单TCL内容
        test_tcl = """
# 简单框架结构测试
wipe
model basic -ndm 2 -ndf 3
node 1 0.0 0.0
node 2 4.0 0.0
node 3 0.0 3.5
node 4 4.0 3.5
fix 1 1 1 0
fix 2 1 1 0
uniaxialMaterial Elastic 1 200000.0
section Elastic 1 200000.0 2000.0 1000000.0
geomTransf Linear 1
element elasticBeamColumn 1 1 3 2000.0 200000.0 1000000.0 1
element elasticBeamColumn 2 2 4 2000.0 200000.0 1000000.0 1
element elasticBeamColumn 3 3 4 2000.0 200000.0 1000000.0 1
pattern Plain 1 Linear {
    load 3 0.0 -50.0 0.0
    load 4 0.0 -50.0 0.0
}
system BandSPD
numberer Plain
constraints Plain
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
"""
        
        # 测试分析
        test_prompt = "计算内力"
        print(f"测试prompt: {test_prompt}")
        print("开始分析...")
        
        result = analyzer.analyze_structure(test_prompt, test_tcl)
        
        # 显示结果摘要
        summary = analyzer.get_analysis_summary(result)
        print(summary)
        
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        print("请设置环境变量: export GEMINI_API_KEY='your-key'")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    main()
