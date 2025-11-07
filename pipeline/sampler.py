"""
从data文件夹中选择用户意图和结构类型的组合
"""
import json
import os
import re
from typing import Tuple, List, Optional, Dict, Set


class Sampler:
    """从data文件夹中选择组合"""
    
    # 中英文映射（与inference.py和postprocess.py保持一致）
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
    
    def __init__(self, data_dir: str = "data", output_dir: str = "output"):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.intentions = []
        self.structures = []
        self._run_count: Optional[int] = None
        self._plan: List[Tuple[str, str, int]] = []
        self._plan_index: int = 0
        self._load_data()
    
    def _translate_to_english(self, structure: str, intention: str) -> Tuple[str, str]:
        """将中文结构类型和意图类型转换为英文"""
        structure_key = structure.strip()
        if structure_key.endswith("结构") and structure_key not in self.STRUCTURE_MAP:
            structure_key = structure_key[:-2]
        structure_en = self.STRUCTURE_MAP.get(structure_key, structure_key.lower().replace(" ", "-"))
        
        intention_key = intention.strip()
        intention_en = self.INTENTION_MAP.get(intention_key, intention_key.lower().replace(" ", "-"))
        return structure_en, intention_en
    
    def _detect_existing_runs(self) -> Dict[Tuple[str, str], Set[int]]:
        """
        检测output文件夹中已存在的组合和次数
        
        Returns:
            Dict[(structure_en, intention_en), Set[run_index]]: 已存在的组合及其run_index集合
        """
        existing_runs: Dict[Tuple[str, str], Set[int]] = {}
        
        if not os.path.exists(self.output_dir):
            return existing_runs
        
        # 检查output文件夹中的文件夹
        for item in os.listdir(self.output_dir):
            item_path = os.path.join(self.output_dir, item)
            if os.path.isdir(item_path) and item != "report":
                # 匹配格式：{structure_en}-{intention_en}-{run_index}
                # 从右往左匹配，确保最后一个数字是run_index
                match = re.match(r'^(.+)-(\d+)$', item)
                if match:
                    prefix, run_index_str = match.groups()
                    run_index = int(run_index_str)
                    # 从prefix中分离structure和intention（最后一个连字符分割）
                    last_dash = prefix.rfind('-')
                    if last_dash > 0:
                        structure_en = prefix[:last_dash]
                        intention_en = prefix[last_dash+1:]
                        key = (structure_en, intention_en)
                        if key not in existing_runs:
                            existing_runs[key] = set()
                        existing_runs[key].add(run_index)
        
        # 检查report文件夹中的报告文件
        report_dir = os.path.join(self.output_dir, "report")
        if os.path.exists(report_dir):
            for item in os.listdir(report_dir):
                if item.endswith('.md'):
                    # 匹配格式：{structure_en}-{intention_en}-{run_index}.md
                    # 从右往左匹配，确保最后一个数字是run_index
                    base_name = item[:-3]  # 移除 .md
                    match = re.match(r'^(.+)-(\d+)$', base_name)
                    if match:
                        prefix, run_index_str = match.groups()
                        run_index = int(run_index_str)
                        # 从prefix中分离structure和intention（最后一个连字符分割）
                        last_dash = prefix.rfind('-')
                        if last_dash > 0:
                            structure_en = prefix[:last_dash]
                            intention_en = prefix[last_dash+1:]
                            key = (structure_en, intention_en)
                            if key not in existing_runs:
                                existing_runs[key] = set()
                            existing_runs[key].add(run_index)
        
        return existing_runs
    
    def _load_data(self):
        """加载intentions.json和structures.json"""
        intentions_path = os.path.join(self.data_dir, "intentions.json")
        structures_path = os.path.join(self.data_dir, "structures.json")
        
        try:
            with open(intentions_path, 'r', encoding='utf-8') as f:
                self.intentions = json.load(f)
            with open(structures_path, 'r', encoding='utf-8') as f:
                self.structures = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"数据文件未找到: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"数据文件格式错误: {e}")
    
    def _ask_run_count(self) -> int:
        """询问用户每个组合需要生成的次数"""
        prompt_text = "请输入本次评测每个结构-意图组合需要生成的次数(正整数): "
        while True:
            user_input = input(prompt_text).strip()
            try:
                value = int(user_input)
                if value <= 0:
                    raise ValueError
                return value
            except ValueError:
                print("输入无效，请输入大于0的整数。")

    def get_run_count(self) -> int:
        """获取每个组合需要生成的次数"""
        if self._run_count is None:
            self._run_count = self._ask_run_count()
        return self._run_count

    def generate_plan(self) -> List[Tuple[str, str, int]]:
        """生成所有结构-意图组合及其对应的轮次计划，跳过已存在的组合"""
        if not self.intentions or not self.structures:
            raise ValueError("数据未加载或为空")

        run_count = self.get_run_count()
        
        # 检测已存在的组合
        existing_runs = self._detect_existing_runs()
        
        plan: List[Tuple[str, str, int]] = []
        skipped_count = 0

        for structure in self.structures:
            for intention in self.intentions:
                # 转换为英文名称
                structure_en, intention_en = self._translate_to_english(structure, intention)
                key = (structure_en, intention_en)
                
                # 获取已存在的run_index
                existing_indices = existing_runs.get(key, set())
                
                # 只生成缺失的run_index
                for run_index in range(1, run_count + 1):
                    if run_index not in existing_indices:
                        plan.append((structure, intention, run_index))
                    else:
                        skipped_count += 1
                        print(f"跳过已存在的组合: {structure_en}-{intention_en}-{run_index}")

        if skipped_count > 0:
            print(f"\n已跳过 {skipped_count} 个已存在的组合。")
        
        self._plan = plan
        self._plan_index = 0
        return plan

    def sample(self) -> Tuple[str, str, int]:
        """
        顺序返回计划中的每个组合，供兼容旧接口使用。

        Returns:
            Tuple[str, str, int]: (结构类型, 用户意图, 当前轮次)
        """
        if not self._plan:
            self.generate_plan()

        if self._plan_index >= len(self._plan):
            raise StopIteration("所有结构-意图组合均已生成。")

        result = self._plan[self._plan_index]
        self._plan_index += 1
        return result


