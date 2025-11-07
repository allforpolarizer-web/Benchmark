"""
从data文件夹中选择用户意图和结构类型的组合
"""
import json
import os
from typing import Tuple, List, Optional


class Sampler:
    """从data文件夹中选择组合"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.intentions = []
        self.structures = []
        self._run_count: Optional[int] = None
        self._plan: List[Tuple[str, str, int]] = []
        self._plan_index: int = 0
        self._load_data()
    
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
        """生成所有结构-意图组合及其对应的轮次计划"""
        if not self.intentions or not self.structures:
            raise ValueError("数据未加载或为空")

        run_count = self.get_run_count()
        plan: List[Tuple[str, str, int]] = []

        for structure in self.structures:
            for intention in self.intentions:
                for run_index in range(1, run_count + 1):
                    plan.append((structure, intention, run_index))

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


