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
        # 本地 OpenSees 可执行程序优先级（可通过环境变量覆盖）
        self.opensees_cmd_candidates = [
            os.environ.get("OPENSEES_CMD"),
            # 添加指定的OpenSees路径
            r"D:\OpenSees3.7.1\bin\OpenSees.exe",
            r"D:\OpenSees3.7.1\bin\OpenSees",
            "OpenSees.exe",
            "OpenSees",
            "opensees.exe",
            "opensees",
        ]

    def _find_opensees_cmd(self) -> Optional[str]:
        """查找可用的本地 OpenSees 可执行程序"""
        for cmd in self.opensees_cmd_candidates:
            if not cmd:
                continue
            try:
                # 如果是绝对路径，直接检查文件是否存在
                if os.path.isabs(cmd) and os.path.isfile(cmd):
                    return cmd
                
                # 尝试相对路径
                if os.path.isfile(cmd):
                    return os.path.abspath(cmd)
                
                # 使用which查找PATH中的命令
                from shutil import which
                found = which(cmd)
                if found:
                    return found
            except Exception:
                continue
        return None

    def verify_with_local_opensees(self, tcl_content: str, timeout: int = 60) -> Dict[str, Any]:
        """
        使用本地 OpenSees 可执行程序运行给定的 TCL 内容，验证是否可正确执行。

        返回:
          {
            'available': bool,        # 是否找到本地 OpenSees
            'invoked': bool,          # 是否成功发起执行
            'passed': bool,           # 返回码为0认为通过
            'return_code': int|None,
            'stdout': str,
            'stderr': str,
            'cmd': str|None,
            'tcl_file': str|None,
            'elapsed_seconds': float|None,
            'message': str            # 简要说明
          }
        """
        import tempfile
        import subprocess
        import time as _time

        result: Dict[str, Any] = {
            "available": False,
            "invoked": False,
            "passed": False,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "cmd": None,
            "tcl_file": None,
            "elapsed_seconds": None,
            "message": ""
        }

        cmd = self._find_opensees_cmd()
        if not cmd:
            result["message"] = "未找到本地 OpenSees 可执行程序（可设置OPENSEES_CMD或加入PATH）"
            return result

        result["available"] = True
        result["cmd"] = cmd

        # 将 TCL 内容写到临时文件
        try:
            temp_dir = Path("temp_opensees")
            temp_dir.mkdir(exist_ok=True)
            tmp = tempfile.NamedTemporaryFile(prefix="verify_", suffix=".tcl", dir=str(temp_dir), delete=False)
            tmp.write(tcl_content.encode("utf-8"))
            tmp.flush()
            tmp.close()
            result["tcl_file"] = tmp.name
        except Exception as e:
            result["message"] = f"写入临时TCL失败: {type(e).__name__}: {e}"
            return result

        # 执行本地 OpenSees
        try:
            start = _time.time()
            proc = subprocess.run([cmd, result["tcl_file"]], capture_output=True, text=True, timeout=timeout, cwd=str(Path(result["tcl_file"]).parent))
            elapsed = _time.time() - start
            result["elapsed_seconds"] = elapsed
            result["invoked"] = True
            result["return_code"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["passed"] = (proc.returncode == 0)
            
            # 提取关键结果信息
            result["output_summary"] = self._extract_opensees_results(proc.stdout, proc.stderr)
            
            if result["passed"]:
                result["message"] = "本地OpenSees执行成功（返回码0）"
            else:
                result["message"] = f"本地OpenSees执行失败（返回码{proc.returncode}）"
        except subprocess.TimeoutExpired:
            result["message"] = f"本地OpenSees执行超时（>{timeout}s）"
        except FileNotFoundError:
            result["message"] = "未找到OpenSees可执行程序"
        except Exception as e:
            result["message"] = f"执行异常: {type(e).__name__}: {e}"

        return result
    
    def _extract_opensees_results(self, stdout: str, stderr: str) -> str:
        """从OpenSees输出中提取关键结果信息"""
        output_lines = (stdout + "\n" + stderr).split('\n')
        summary = []
        
        # 查找是否有执行成功的标识
        for line in output_lines:
            if "analyze 1" in line.lower() or "分析成功" in line or "静态分析成功" in line:
                summary.append(f"分析状态: {line.strip()}")
            elif "位移" in line or "displacement" in line.lower():
                summary.append(f"位移: {line.strip()}")
            elif "频率" in line or "frequency" in line.lower():
                summary.append(f"频率: {line.strip()}")
            elif "omega" in line.lower():
                summary.append(f"圆频率: {line.strip()}")
        
        # 如果没有找到关键信息，提取错误信息
        if not summary:
            for line in output_lines:
                if "ERROR" in line or "WARNING" in line:
                    summary.append(f"警告: {line.strip()}")
        
        return "\n".join(summary[:10]) if summary else "无额外输出"
    
    def compare_results(self, llm_result: Dict[str, Any], local_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        对比LLM生成的结果和本地OpenSees验证的结果
        
        Returns:
            {
                'comparable': bool,      # 是否可以对比
                'consistent': bool,      # 结果是否一致
                'comparison_details': str # 对比详情
            }
        """
        comparison = {
            "comparable": False,
            "consistent": False,
            "comparison_details": ""
        }
        
        # 检查是否都有有效的执行结果
        llm_exec = llm_result.get("execution_result", {})
        local_exec = local_result
        
        has_llm_result = llm_result.get("success", False) and llm_exec.get("success", False)
        has_local_result = local_exec.get("passed", False)
        
        if not has_llm_result or not has_local_result:
            comparison["comparison_details"] = f"LLM结果: {has_llm_result}, 本地结果: {has_local_result}"
            return comparison
        
        comparison["comparable"] = True
        
        # 提取关键数据进行对比
        llm_output = llm_exec.get("stdout", "")
        local_output = local_exec.get("stdout", "") + "\n" + local_exec.get("stderr", "")
        
        # 提取数值结果进行对比（如果有位移、频率等）
        llm_values = self._extract_numerical_values(llm_output)
        local_values = self._extract_numerical_values(local_output)
        
        details = []
        details.append("LLM结果摘要:")
        details.append(llm_output[:500] if llm_output else "无输出")
        details.append("\n本地OpenSees结果摘要:")
        details.append(local_exec.get("output_summary", "无摘要"))
        
        # 简单的对比逻辑
        if llm_values and local_values:
            details.append(f"\nLLM提取的数值: {llm_values}")
            details.append(f"本地OpenSees提取的数值: {local_values}")
            
            # 简单的数值一致性检查
            llm_numbers = [float(v) for v in llm_values if v.replace('.', '').replace('-', '').isdigit()]
            local_numbers = [float(v) for v in local_values if v.replace('.', '').replace('-', '').isdigit()]
            
            if llm_numbers and local_numbers and len(llm_numbers) == len(local_numbers):
                # 简单对比：数值在同一数量级
                differences = [abs(llm_numbers[i] - local_numbers[i]) / abs(local_numbers[i]) if local_numbers[i] != 0 else 0 
                               for i in range(min(len(llm_numbers), len(local_numbers)))]
                
                avg_diff = sum(differences) / len(differences) if differences else 1.0
                comparison["consistent"] = avg_diff < 0.1  # 允许10%误差
                details.append(f"数值对比: 平均差异 {avg_diff*100:.2f}%")
            else:
                details.append("数值数量和类型不完全匹配")
                comparison["consistent"] = False
        else:
            # 如果没有数值，就检查是否都有成功的输出
            comparison["consistent"] = has_llm_result and has_local_result
            details.append("无法进行数值对比，仅检查执行状态")
        
        comparison["comparison_details"] = "\n".join(details)
        return comparison
    
    def _extract_numerical_values(self, text: str) -> list:
        """从文本中提取数值"""
        import re
        # 提取浮点数
        numbers = re.findall(r'-?\d+\.?\d*(?:e[+-]?\d+)?', text)
        return numbers
    
    def save_analysis_result(self, result: Dict[str, Any], 
                           intention: str = None, 
                           structure_type: str = None,
                           custom_filename: str = None,
                           verification: Optional[Dict[str, Any]] = None,
                           comparison: Optional[Dict[str, Any]] = None) -> str:
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
            },
            "verification": verification or {},
            "comparison": comparison or {}
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
                        structure_type: str = None,
                        verification: Optional[Dict[str, Any]] = None,
                        comparison: Optional[Dict[str, Any]] = None) -> str:
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

        # 验证结论
        text_content.append("-" * 40)
        text_content.append("4. 本地OpenSees验证")
        text_content.append("-" * 40)
        if verification:
            passed = verification.get("passed", False)
            msg = verification.get("message", "")
            cmd = verification.get("cmd", "")
            rc = verification.get("return_code", None)
            text_content.append(f"验证结论: {'通过' if passed else '未通过'}")
            text_content.append(f"验证说明: {msg}")
            if cmd:
                text_content.append(f"命令: {cmd}")
            if rc is not None:
                text_content.append(f"返回码: {rc}")
            
            # 添加本地OpenSees的输出摘要
            output_summary = verification.get("output_summary", "")
            if output_summary and output_summary != "无额外输出":
                text_content.append(f"\n本地OpenSees输出摘要:")
                text_content.append(output_summary)
        else:
            text_content.append("验证结论: 未执行（未提供验证信息）")
        text_content.append("")
        
        # 对比结果
        if comparison:
            text_content.append("-" * 40)
            text_content.append("5. LLM结果与本地OpenSees对比")
            text_content.append("-" * 40)
            text_content.append(f"可对比: {'是' if comparison.get('comparable') else '否'}")
            text_content.append(f"结果一致性: {'一致' if comparison.get('consistent') else '不一致'}")
            text_content.append(f"\n对比详情:")
            text_content.append(comparison.get("comparison_details", ""))
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
