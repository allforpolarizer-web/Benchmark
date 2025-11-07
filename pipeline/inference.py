"""
通过llm.py调用gemini api根据prompt编写openseespy程序，运行并迭代修改
"""
# -*- coding: utf-8 -*-
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
import json
from typing import Optional, List, Dict, Tuple
from llm import GeminiClient
from pipeline.preprocess import EnvironmentManager


class InferenceEngine:
    """迭代生成和运行openseespy程序"""
    
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
        self.env_manager = EnvironmentManager()
        self.python_exe = None
        self.max_iterations = 10
    
    def _translate_to_english(self, structure: str, intention: str) -> Tuple[str, str]:
        """将中文结构类型和意图类型转换为英文"""
        structure_key = structure.strip()
        if structure_key.endswith("结构") and structure_key not in self.STRUCTURE_MAP:
            structure_key = structure_key[:-2]
        structure_en = self.STRUCTURE_MAP.get(structure_key, structure_key.lower().replace(" ", "-"))

        intention_key = intention.strip()
        intention_en = self.INTENTION_MAP.get(intention_key, intention_key.lower().replace(" ", "-"))
        return structure_en, intention_en
    
    def _ensure_output_dir(self, folder_name: str):
        """确保输出目录存在"""
        folder_path = os.path.join(self.output_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path
    
    def _get_python_executable(self) -> str:
        """获取Python可执行文件路径"""
        if self.python_exe is None:
            self.python_exe = self.env_manager.get_python_executable()
        return self.python_exe
    
    def _generate_code(self, prompt: str, iteration: int, previous_code: Optional[str] = None, 
                      previous_error: Optional[str] = None) -> str:
        """
        生成openseespy代码
        
        Args:
            prompt: 用户需求prompt
            iteration: 当前迭代次数
            previous_code: 上一次的代码（如果有）
            previous_error: 上一次运行错误（如果有）
        
        Returns:
            生成的代码
        """
        if iteration == 1 or not previous_code:
            # 第一次生成
            system_prompt = f"""你是一个结构分析专家，擅长使用OpenSeesPy进行结构分析。

用户需求：{prompt}

请根据用户需求，使用OpenSeesPy编写一个完整的结构分析程序。要求：
1. 使用openseespy.opensees模块
2. 所有注释使用中文
3. 代码完整，可以直接运行
4. 包含必要的模型定义、分析步骤和结果输出
5. 确保代码语法正确
6. 不要包含绘图、可视化、matplotlib等绘图相关的代码，只输出数值计算结果

只输出Python代码，不要包含任何解释或markdown格式："""
        else:
            # 迭代修改
            system_prompt = f"""你是一个结构分析专家，需要修复OpenSeesPy程序中的错误。

用户需求：{prompt}

上一次的代码：
```python
{previous_code}
```

运行错误信息：
{previous_error}

请根据错误信息修改代码，要求：
1. 修复所有错误
2. 保持代码完整可运行
3. 所有注释使用中文
4. 不要包含绘图、可视化、matplotlib等绘图相关的代码，只输出数值计算结果
5. 只输出修改后的完整Python代码，不要包含任何解释或markdown格式："""
        
        code = self.client.call(system_prompt)
        
        if not code:
            raise RuntimeError("生成代码失败")
        
        # 清理代码（移除可能的markdown格式）
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()
        
        return code
    
    def _save_code(self, code: str, structure: str, intention: str, iteration: int, run_index: int) -> str:
        """
        保存代码到文件
        
        Returns:
            保存的文件路径
        """
        # 转换为英文名称
        structure_en, intention_en = self._translate_to_english(structure, intention)
        
        folder_name = f"{structure_en}-{intention_en}-{run_index}"
        folder_path = self._ensure_output_dir(folder_name)
        
        filename = f"{structure_en}-{intention_en}-{run_index}-{iteration}.py"
        filepath = os.path.join(folder_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        
        return filepath
    
    def _run_code(self, filepath: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        运行代码
        
        Returns:
            (是否成功, 标准输出, 错误输出)
        """
        python_exe = self._get_python_executable()
        
        try:
            result = subprocess.run(
                [python_exe, filepath],
                capture_output=True,
                text=True,
                timeout=300,  # 延长到5分钟
                encoding='utf-8',
                errors='ignore'
            )
            
            success = result.returncode == 0
            stdout = result.stdout if result.stdout else None
            stderr = result.stderr if result.stderr else None
            
            return success, stdout, stderr
        except subprocess.TimeoutExpired:
            return False, None, "程序运行超时（300秒）"
        except Exception as e:
            return False, None, f"运行异常: {str(e)}"
    
    def _analyze_result(self, success: bool, stdout: Optional[str], stderr: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        通过LLM分析运行结果，判断是否成功
        
        Returns:
            (是否成功, 错误信息或None)
        """
        if success:
            # 即使返回码为0，也通过LLM确认是否真的成功
            analysis_prompt = f"""请分析以下OpenSeesPy程序的运行结果，判断程序是否成功执行。

标准输出：
{stdout if stdout else "无输出"}

错误输出：
{stderr if stderr else "无错误"}

请判断：
1. 程序是否成功执行？
2. 如果失败，请说明失败原因

只回答"成功"或"失败：原因"，不要其他解释："""
        else:
            analysis_prompt = f"""请分析以下OpenSeesPy程序的运行错误：

标准输出：
{stdout if stdout else "无输出"}

错误输出：
{stderr if stderr else "无错误"}

请提取关键错误信息，用于修复代码。只输出错误原因，不要其他解释："""
        
        analysis = self.client.call(analysis_prompt)
        
        if not analysis:
            # 如果LLM分析失败，使用简单的判断
            return success, stderr
        
        analysis = analysis.strip()
        
        if "成功" in analysis or success:
            return True, None
        else:
            return False, analysis or stderr
    
    def run(self, prompt: str, structure: str, intention: str, run_index: int) -> Dict:
        """
        运行推理流程
        
        Args:
            prompt: 用户需求prompt
            structure: 结构类型
            intention: 用户意图
        
        Returns:
            包含迭代信息的字典
        """
        print(f"\n{'='*60}")
        print(f"开始推理流程: {structure}-{intention} (第 {run_index} 次)")
        print(f"{'='*60}\n")
        
        previous_code = None
        previous_error = None
        iterations_info = []
        
        for iteration in range(1, self.max_iterations + 1):
            print(f"\n--- 迭代 {iteration}/{self.max_iterations} ---")
            
            try:
                # 生成代码
                print("正在生成代码...")
                code = self._generate_code(prompt, iteration, previous_code, previous_error)
                
                # 保存代码
                filepath = self._save_code(code, structure, intention, iteration, run_index)
                print(f"代码已保存: {filepath}")
                
                # 运行代码
                print("正在运行代码...")
                success, stdout, stderr = self._run_code(filepath)
                
                # 分析结果
                print("正在分析运行结果...")
                is_success, error_info = self._analyze_result(success, stdout, stderr)
                
                iteration_info = {
                    "iteration": iteration,
                    "filepath": filepath,
                    "success": is_success,
                    "stdout": stdout,
                    "stderr": stderr,
                    "error_info": error_info
                }
                iterations_info.append(iteration_info)
                
                if is_success:
                    print(f"✅ 迭代 {iteration} 成功！")
                    break
                else:
                    print(f"❌ 迭代 {iteration} 失败")
                    if error_info:
                        print(f"错误信息: {error_info}")
                    
                    if iteration < self.max_iterations:
                        print("准备修改代码...")
                        previous_code = code
                        previous_error = error_info or stderr
                    else:
                        print("已达到最大迭代次数，停止迭代")
            except Exception as e:
                print(f"❌ 迭代 {iteration} 发生异常: {e}")
                iteration_info = {
                    "iteration": iteration,
                    "filepath": None,
                    "success": False,
                    "error": str(e)
                }
                iterations_info.append(iteration_info)

                previous_error = str(e)

                if iteration < self.max_iterations:
                    print("将在下一次迭代中重试生成代码...")
                    continue
                else:
                    break
        
        result = {
            "structure": structure,
            "intention": intention,
            "prompt": prompt,
            "iterations": iterations_info,
            "final_success": iterations_info[-1]["success"] if iterations_info else False,
            "run_index": run_index
        }
        
        return result

