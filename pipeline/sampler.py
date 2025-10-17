#!/usr/bin/env python3
"""
sampler.py - 根据data文件夹随机选择用户意图和结构类型的组合
用户意图三类：内力反力、位移变形、模态分析
结构种类三类：框架、剪力墙、框架剪力墙
总共3*3=9种组合
"""

import json
import random
from pathlib import Path
from typing import Dict, Tuple


class DataSampler:
    def __init__(self, data_dir: str = "data"):
        """初始化数据采样器"""
        self.data_dir = Path(data_dir)
        self.intentions = self._load_intentions()
        self.structures = self._load_structures()
        
    def _load_intentions(self) -> list:
        """加载用户意图数据"""
        intentions_file = self.data_dir / "intentions.json"
        try:
            with open(intentions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告：未找到 {intentions_file}")
            return ["内力反力", "位移变形", "模态分析"]
        except json.JSONDecodeError as e:
            print(f"错误：解析 {intentions_file} 失败 - {e}")
            return ["内力反力", "位移变形", "模态分析"]
    
    def _load_structures(self) -> list:
        """加载结构类型数据"""
        structures_file = self.data_dir / "structures.json"
        try:
            with open(structures_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"警告：未找到 {structures_file}")
            return ["框架", "剪力墙", "框架剪力墙"]
        except json.JSONDecodeError as e:
            print(f"错误：解析 {structures_file} 失败 - {e}")
            return ["框架", "剪力墙", "框架剪力墙"]
    
    def sample_combination(self) -> Tuple[str, str]:
        """随机采样一个用户意图和结构类型的组合"""
        intention = random.choice(self.intentions)
        structure = random.choice(self.structures)
        return intention, structure
    
    def get_all_combinations(self) -> list:
        """获取所有可能的组合"""
        combinations = []
        for intention in self.intentions:
            for structure in self.structures:
                combinations.append((intention, structure))
        return combinations
    
    def sample_multiple(self, count: int) -> list:
        """采样多个组合"""
        combinations = []
        for _ in range(count):
            combinations.append(self.sample_combination())
        return combinations
    
    def get_info(self) -> Dict:
        """获取采样器信息"""
        return {
            "intentions": self.intentions,
            "structures": self.structures,
            "total_combinations": len(self.intentions) * len(self.structures),
            "all_combinations": self.get_all_combinations()
        }


def main():
    """测试函数"""
    print("=== 数据采样器测试 ===")
    
    sampler = DataSampler()
    info = sampler.get_info()
    
    print(f"用户意图: {info['intentions']}")
    print(f"结构类型: {info['structures']}")
    print(f"总组合数: {info['total_combinations']}")
    print(f"所有组合: {info['all_combinations']}")
    
    print("\n随机采样测试:")
    for i in range(5):
        intention, structure = sampler.sample_combination()
        print(f"  第{i+1}次: 意图={intention}, 结构={structure}")


if __name__ == "__main__":
    main()