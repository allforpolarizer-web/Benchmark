"""
主控制流程
"""
# -*- coding: utf-8 -*-
import os
import sys
# 设置控制台编码为UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass
from pipeline.sampler import Sampler
from pipeline.prompt import PromptGenerator
from pipeline.preprocess import EnvironmentManager
from pipeline.inference import InferenceEngine
from pipeline.postprocess import PostProcessor


def main():
    """主函数"""
    print("=" * 60)
    print("结构分析助手 Benchmark")
    print("=" * 60)
    
    # 获取API密钥
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ 错误: 未设置GEMINI_API_KEY环境变量")
        print("请设置环境变量: set GEMINI_API_KEY=your-api-key (Windows)")
        return
    
    try:
        # 1. 生成评测计划
        print("\n[1/4] 生成评测计划...")
        sampler = Sampler()
        plan = sampler.generate_plan()
        run_count = sampler.get_run_count()
        total_tasks = len(plan)

        if total_tasks == 0:
            print("⚠️ 未找到任何结构或意图组合，结束流程。")
            return

        print(f"✅ 计划生成完成: 共 {total_tasks} 个任务，每个组合生成 {run_count} 次。")

        # 2. 初始化LLM客户端
        print("\n[2/4] 初始化LLM客户端...")
        prompt_generator = PromptGenerator(api_key=api_key)
        inference_engine = InferenceEngine(api_key=api_key)
        post_processor = PostProcessor(api_key=api_key)
        print("✅ LLM客户端初始化完成")

        # 3. 预处理：检查openseespy环境
        print("\n[3/4] 检查OpenSeesPy环境...")
        env_manager = EnvironmentManager()
        env_manager.setup_environment()
        print("✅ 环境检查完成")

        # 4. 执行评测任务
        print("\n[4/4] 开始执行评测任务...")
        report_paths = []

        for idx, (structure, intention, run_index) in enumerate(plan, start=1):
            print("\n" + "-" * 60)
            print(f"任务 {idx}/{total_tasks}: {structure}-{intention} (第 {run_index} 次)")
            print("-" * 60)

            try:
                prompt = prompt_generator.generate(intention, structure)
                inference_result = inference_engine.run(prompt, structure, intention, run_index)
                report_path = post_processor.evaluate(inference_result)
                report_paths.append(report_path)
            except Exception as task_error:
                print(f"❌ 任务 {idx} 失败: {task_error}")
                continue

        print("\n" + "=" * 60)
        print("✅ Benchmark 完成！")
        if report_paths:
            print("📊 生成的评测报告:")
            for path in report_paths:
                print(f"  - {path}")
        else:
            print("⚠️ 没有成功生成评测报告")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()

