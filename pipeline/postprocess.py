#!/usr/bin/env python3
"""
postprocess.py - 将prompt、TCL描述和Gemini回答保存到output文件夹
保存内容包括：
1. prompt.py生成的prompt
2. preprocess.py生成的TCL结构描述  
3. Gemini API的回答
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class ResultPostprocessor:
    def __init__(self, output_dir: str = "output"):
        """初始化结果后处理器"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def save_analysis_result(self, result: Dict[str, Any], 
                           intention: str = None, 
                           structure_type: str = None,
                           custom_filename: str = None) -> str:
        """
        保存分析结果到文件
        
        Args:
            result: 分析结果字典
            intention: 用户意图
            structure_type: 结构类型
            custom_filename: 自定义文件名
        
        Returns:
            保存的文件路径
        """
        # 生成文件名
        if custom_filename:
            filename = custom_filename
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            intention_suffix = f"_{intention}" if intention else ""
            structure_suffix = f"_{structure_type}" if structure_type else ""
            filename = f"analysis_{timestamp}{intention_suffix}{structure_suffix}.json"
        
        file_path = self.output_dir / filename
        
        # 准备保存的数据
        save_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "intention": intention,
                "structure_type": structure_type,
                "filename": filename
            },
            "prompt": result.get("prompt", ""),
            "tcl_content": result.get("tcl_content", ""),
            "analysis_result": {
                "success": result.get("success", False),
                "think_response": result.get("think_response", ""),
                "code_response": result.get("code_response", ""),
                "extracted_code": result.get("extracted_code", ""),
                "execution_result": result.get("execution_result", {}),
                "errors": result.get("errors", []),
                "failed_steps": result.get("failed_steps", [])
            }
        }
        
        # 保存到JSON文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 分析结果已保存到: {file_path}")
            return str(file_path)
            
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
            return ""
    
    def save_text_result(self, prompt: str, tcl_content: str, 
                        gemini_response: str, intention: str = None,
                        structure_type: str = None) -> str:
        """
        保存为文本格式（更易读）
        
        Args:
            prompt: 用户prompt
            tcl_content: TCL结构描述
            gemini_response: Gemini API回答
            intention: 用户意图
            structure_type: 结构类型
        
        Returns:
            保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        intention_suffix = f"_{intention}" if intention else ""
        structure_suffix = f"_{structure_type}" if structure_type else ""
        filename = f"result_{timestamp}{intention_suffix}{structure_suffix}.txt"
        
        file_path = self.output_dir / filename
        
        # 准备文本内容
        text_content = []
        text_content.append("=" * 80)
        text_content.append("结构分析助手 - Benchmark结果")
        text_content.append("=" * 80)
        text_content.append("")
        
        text_content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if intention:
            text_content.append(f"用户意图: {intention}")
        if structure_type:
            text_content.append(f"结构类型: {structure_type}")
        text_content.append("")
        
        text_content.append("-" * 40)
        text_content.append("1. 用户Prompt")
        text_content.append("-" * 40)
        text_content.append(prompt)
        text_content.append("")
        
        text_content.append("-" * 40)
        text_content.append("2. TCL结构描述")
        text_content.append("-" * 40)
        text_content.append(tcl_content)
        text_content.append("")
        
        text_content.append("-" * 40)
        text_content.append("3. Gemini API回答")
        text_content.append("-" * 40)
        text_content.append(gemini_response)
        text_content.append("")
        
        text_content.append("=" * 80)
        text_content.append("分析完成")
        text_content.append("=" * 80)
        
        # 保存到文本文件
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(text_content))
            
            print(f"✅ 文本结果已保存到: {file_path}")
            return str(file_path)
            
        except Exception as e:
            print(f"❌ 保存文本文件失败: {e}")
            return ""
    
    def save_batch_results(self, results: list, batch_name: str = None) -> str:
        """
        批量保存多个分析结果
        
        Args:
            results: 分析结果列表
            batch_name: 批次名称
        
        Returns:
            保存的批次文件路径
        """
        if batch_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_name = f"batch_{timestamp}"
        
        filename = f"{batch_name}.json"
        file_path = self.output_dir / filename
        
        # 准备批量数据
        batch_data = {
            "metadata": {
                "batch_name": batch_name,
                "timestamp": datetime.now().isoformat(),
                "total_results": len(results)
            },
            "results": results
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 批量结果已保存到: {file_path}")
            return str(file_path)
            
        except Exception as e:
            print(f"❌ 保存批量文件失败: {e}")
            return ""
    
    def load_result(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        加载之前保存的结果
        
        Args:
            filename: 文件名
        
        Returns:
            加载的结果字典，如果失败返回None
        """
        file_path = self.output_dir / filename
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ 文件不存在: {file_path}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return None
        except Exception as e:
            print(f"❌ 加载文件失败: {e}")
            return None
    
    def list_results(self) -> list:
        """列出所有保存的结果文件"""
        try:
            files = []
            for file_path in self.output_dir.glob("*.json"):
                files.append({
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
            return sorted(files, key=lambda x: x["modified"], reverse=True)
        except Exception as e:
            print(f"❌ 列出文件失败: {e}")
            return []
    
    def get_result_summary(self, result: Dict[str, Any]) -> str:
        """获取结果摘要"""
        summary = []
        summary.append("分析结果摘要:")
        summary.append(f"  成功状态: {'成功' if result.get('success') else '失败'}")
        summary.append(f"  用户prompt: {result.get('prompt', 'N/A')}")
        
        if result.get('analysis_result', {}).get('execution_result'):
            exec_result = result['analysis_result']['execution_result']
            summary.append(f"  执行状态: {'成功' if exec_result.get('success') else '失败'}")
        
        if result.get('analysis_result', {}).get('errors'):
            summary.append(f"  错误数量: {len(result['analysis_result']['errors'])}")
        
        return "\n".join(summary)


def main():
    """测试函数"""
    print("=== 结果后处理器测试 ===")
    
    postprocessor = ResultPostprocessor()
    
    # 测试数据
    test_result = {
        "success": True,
        "prompt": "计算内力",
        "tcl_content": "wipe\nmodel basic -ndm 2 -ndf 3\nnode 1 0.0 0.0\nfix 1 1 1 0",
        "think_response": "这是一个简单的结构分析任务",
        "code_response": "生成的Python代码",
        "extracted_code": "import openseespy.opensees as ops\nops.wipe()",
        "execution_result": {
            "success": True,
            "stdout": "分析成功完成"
        },
        "errors": [],
        "failed_steps": []
    }
    
    # 测试保存JSON格式
    print("\n测试保存JSON格式:")
    json_file = postprocessor.save_analysis_result(
        test_result, 
        intention="内力反力", 
        structure_type="框架"
    )
    
    # 测试保存文本格式
    print("\n测试保存文本格式:")
    text_file = postprocessor.save_text_result(
        prompt="计算内力",
        tcl_content="wipe\nmodel basic -ndm 2 -ndf 3",
        gemini_response="这是一个结构分析的回答",
        intention="内力反力",
        structure_type="框架"
    )
    
    # 测试列出文件
    print("\n已保存的文件:")
    files = postprocessor.list_results()
    for file_info in files:
        print(f"  {file_info['filename']} ({file_info['size']} bytes)")
    
    # 测试加载结果
    if json_file:
        print(f"\n测试加载结果: {json_file}")
        loaded_result = postprocessor.load_result(Path(json_file).name)
        if loaded_result:
            summary = postprocessor.get_result_summary(loaded_result)
            print(summary)


if __name__ == "__main__":
    main()