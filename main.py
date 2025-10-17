#!/usr/bin/env python3
"""
main.py - 结构分析助手benchmark主控制流程
协调各个模块完成完整的benchmark流程：
1. sampler.py - 随机选择用户意图和结构类型组合
2. preprocess.py - 根据结构类型生成TCL描述
3. prompt.py - 根据用户意图生成prompt
4. inference.py - 调用Gemini API分析结构
5. postprocess.py - 保存结果到output文件夹
"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, List

# 添加pipeline目录到Python路径
pipeline_dir = Path(__file__).parent / "pipeline"
sys.path.insert(0, str(pipeline_dir))

from sampler import DataSampler
from preprocess import StructurePreprocessor
from prompt import PromptGenerator
from inference import StructureAnalyzer
from postprocess import ResultPostprocessor


class BenchmarkPipeline:
    def __init__(self, api_key: str = None):
        """初始化benchmark流水线"""
        self.sampler = DataSampler()
        self.preprocessor = StructurePreprocessor()
        self.prompt_generator = PromptGenerator(api_key)
        self.analyzer = StructureAnalyzer(api_key)
        self.postprocessor = ResultPostprocessor()
        
        self.results = []
    
    def run_single_benchmark(self, intention: str = None, structure_type: str = None) -> Dict[str, Any]:
        """
        运行单个benchmark测试
        
        Args:
            intention: 用户意图（如果为None则随机采样）
            structure_type: 结构类型（如果为None则随机采样）
        
        Returns:
            完整的benchmark结果
        """
        print("=" * 60)
        print("开始单个benchmark测试")
        print("=" * 60)
        
        # 步骤1: 采样用户意图和结构类型
        if intention is None or structure_type is None:
            sampled_intention, sampled_structure = self.sampler.sample_combination()
            intention = intention or sampled_intention
            structure_type = structure_type or sampled_structure
        
        print(f"步骤1: 采样结果")
        print(f"  用户意图: {intention}")
        print(f"  结构类型: {structure_type}")
        
        # 步骤2: 生成TCL结构描述
        print(f"\n步骤2: 生成{structure_type}结构TCL描述")
        try:
            tcl_content = self.preprocessor.generate_tcl(structure_type)
            print(f"  TCL内容长度: {len(tcl_content)} 字符")
        except Exception as e:
            print(f"  ❌ TCL生成失败: {e}")
            return self._create_error_result(intention, structure_type, f"TCL生成失败: {e}")
        
        # 步骤3: 生成用户prompt
        print(f"\n步骤3: 根据意图'{intention}'生成prompt")
        try:
            prompt = self.prompt_generator.generate_prompt(intention)
            print(f"  生成的prompt: '{prompt}' (长度: {len(prompt)})")
        except Exception as e:
            print(f"  ❌ Prompt生成失败: {e}")
            return self._create_error_result(intention, structure_type, f"Prompt生成失败: {e}")
        
        # 步骤4: 调用Gemini API分析结构
        print(f"\n步骤4: 调用Gemini API分析结构")
        try:
            analysis_result = self.analyzer.analyze_structure(prompt, tcl_content)
            print(f"  分析状态: {'成功' if analysis_result.get('success') else '失败'}")
        except Exception as e:
            print(f"  ❌ 结构分析失败: {e}")
            return self._create_error_result(intention, structure_type, f"结构分析失败: {e}")
        
        # 步骤5: 保存结果
        print(f"\n步骤5: 保存分析结果")
        try:
            # 保存JSON格式
            json_file = self.postprocessor.save_analysis_result(
                analysis_result, intention, structure_type
            )
            
            # 保存文本格式（更易读）
            gemini_response = analysis_result.get('think_response', '') + "\n" + \
                            analysis_result.get('code_response', '')
            text_file = self.postprocessor.save_text_result(
                prompt, tcl_content, gemini_response, intention, structure_type
            )
            
            print(f"  JSON文件: {json_file}")
            print(f"  文本文件: {text_file}")
            
        except Exception as e:
            print(f"  ❌ 结果保存失败: {e}")
        
        # 整理完整结果
        complete_result = {
            "intention": intention,
            "structure_type": structure_type,
            "prompt": prompt,
            "tcl_content": tcl_content,
            "analysis_result": analysis_result,
            "json_file": json_file if 'json_file' in locals() else "",
            "text_file": text_file if 'text_file' in locals() else "",
            "timestamp": time.time()
        }
        
        self.results.append(complete_result)
        
        print(f"\n✅ 单个benchmark测试完成")
        return complete_result
    
    def run_batch_benchmark(self, count: int = 9) -> List[Dict[str, Any]]:
        """
        运行批量benchmark测试
        
        Args:
            count: 测试数量（默认9个，覆盖所有组合）
        
        Returns:
            批量测试结果列表
        """
        print("=" * 60)
        print(f"开始批量benchmark测试 (共{count}个)")
        print("=" * 60)
        
        batch_results = []
        
        for i in range(count):
            print(f"\n--- 第 {i+1}/{count} 个测试 ---")
            result = self.run_single_benchmark()
            batch_results.append(result)
            
            # 添加延迟避免API限制
            if i < count - 1:
                print("等待2秒...")
                time.sleep(2)
        
        # 保存批量结果
        print(f"\n保存批量结果...")
        batch_file = self.postprocessor.save_batch_results(batch_results, f"batch_{int(time.time())}")
        print(f"批量结果文件: {batch_file}")
        
        # 统计结果
        self._print_batch_summary(batch_results)
        
        return batch_results
    
    def run_all_combinations(self) -> List[Dict[str, Any]]:
        """运行所有可能的组合测试（3x3=9种）"""
        print("=" * 60)
        print("运行所有组合测试 (3x3=9种)")
        print("=" * 60)
        
        all_combinations = self.sampler.get_all_combinations()
        print(f"所有组合: {all_combinations}")
        
        results = []
        for i, (intention, structure_type) in enumerate(all_combinations):
            print(f"\n--- 组合 {i+1}/9: {intention} + {structure_type} ---")
            result = self.run_single_benchmark(intention, structure_type)
            results.append(result)
            
            # 添加延迟避免API限制
            if i < len(all_combinations) - 1:
                print("等待2秒...")
                time.sleep(2)
        
        # 保存所有组合结果
        print(f"\n保存所有组合结果...")
        batch_file = self.postprocessor.save_batch_results(results, "all_combinations")
        print(f"所有组合结果文件: {batch_file}")
        
        # 统计结果
        self._print_batch_summary(results)
        
        return results
    
    def _create_error_result(self, intention: str, structure_type: str, error_msg: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "intention": intention,
            "structure_type": structure_type,
            "prompt": "",
            "tcl_content": "",
            "analysis_result": {
                "success": False,
                "error": error_msg
            },
            "json_file": "",
            "text_file": "",
            "timestamp": time.time()
        }
    
    def _print_batch_summary(self, results: List[Dict[str, Any]]):
        """打印批量测试摘要"""
        print("\n" + "=" * 60)
        print("批量测试摘要")
        print("=" * 60)
        
        total = len(results)
        successful = sum(1 for r in results if r.get('analysis_result', {}).get('success', False))
        failed = total - successful
        
        print(f"总测试数: {total}")
        print(f"成功数: {successful}")
        print(f"失败数: {failed}")
        print(f"成功率: {successful/total*100:.1f}%")
        
        # 按意图统计
        print(f"\n按用户意图统计:")
        intention_stats = {}
        for result in results:
            intention = result.get('intention', 'Unknown')
            if intention not in intention_stats:
                intention_stats[intention] = {'total': 0, 'success': 0}
            intention_stats[intention]['total'] += 1
            if result.get('analysis_result', {}).get('success', False):
                intention_stats[intention]['success'] += 1
        
        for intention, stats in intention_stats.items():
            success_rate = stats['success'] / stats['total'] * 100
            print(f"  {intention}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        
        # 按结构类型统计
        print(f"\n按结构类型统计:")
        structure_stats = {}
        for result in results:
            structure = result.get('structure_type', 'Unknown')
            if structure not in structure_stats:
                structure_stats[structure] = {'total': 0, 'success': 0}
            structure_stats[structure]['total'] += 1
            if result.get('analysis_result', {}).get('success', False):
                structure_stats[structure]['success'] += 1
        
        for structure, stats in structure_stats.items():
            success_rate = stats['success'] / stats['total'] * 100
            print(f"  {structure}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")


def main():
    """主函数"""
    print("=== 结构分析助手 Benchmark ===")
    
    # 检查API密钥
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ 错误: 未设置GEMINI_API_KEY环境变量")
        print("请设置: export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)
    
    try:
        # 初始化benchmark流水线
        pipeline = BenchmarkPipeline(api_key)
        
        # 显示菜单
        print("\n请选择运行模式:")
        print("1. 单个测试 (随机采样)")
        print("2. 批量测试 (指定数量)")
        print("3. 所有组合测试 (3x3=9种)")
        print("4. 退出")
        
        while True:
            try:
                choice = input("\n请输入选择 (1-4): ").strip()
                
                if choice == "1":
                    print("\n运行单个测试...")
                    result = pipeline.run_single_benchmark()
                    print(f"\n测试完成，结果已保存")
                    break
                
                elif choice == "2":
                    try:
                        count = int(input("请输入测试数量 (默认9): ") or "9")
                        print(f"\n运行{count}个批量测试...")
                        results = pipeline.run_batch_benchmark(count)
                        print(f"\n批量测试完成，共{len(results)}个结果")
                        break
                    except ValueError:
                        print("❌ 请输入有效的数字")
                        continue
                
                elif choice == "3":
                    print("\n运行所有组合测试...")
                    results = pipeline.run_all_combinations()
                    print(f"\n所有组合测试完成，共{len(results)}个结果")
                    break
                
                elif choice == "4":
                    print("退出程序")
                    sys.exit(0)
                
                else:
                    print("❌ 无效选择，请输入1-4")
                    continue
                    
            except KeyboardInterrupt:
                print("\n\n用户中断，退出程序")
                sys.exit(0)
            except Exception as e:
                print(f"❌ 发生错误: {e}")
                continue
    
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()