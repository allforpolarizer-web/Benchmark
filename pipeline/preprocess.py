#!/usr/bin/env python3
"""
preprocess.py - 根据结构类型生成TCL描述
根据结构类型采样结果生成相应的TCL结构描述
"""

import random
from typing import Dict, Any


class StructurePreprocessor:
    def __init__(self):
        """初始化结构预处理器"""
        pass
    
    def generate_tcl(self, structure_type: str, **kwargs) -> str:
        """根据结构类型生成TCL描述"""
        if structure_type == "框架":
            return self._generate_framework_tcl(**kwargs)
        elif structure_type == "剪力墙":
            return self._generate_shearwall_tcl(**kwargs)
        elif structure_type == "框架剪力墙":
            return self._generate_frame_shearwall_tcl(**kwargs)
        else:
            raise ValueError(f"不支持的结构类型: {structure_type}")
    
    def _generate_framework_tcl(self, stories: int = None, bays: int = None, 
                               case_idx: int = None, v_scale: float = None, 
                               h_scale: float = None) -> str:
        """生成框架结构TCL - 基于参考/Framework.py"""
        # 随机参数（如果未提供）
        if stories is None:
            stories = random.randint(2, 6)
        if bays is None:
            bays = random.randint(2, 5)
        if case_idx is None:
            case_idx = random.randint(1, 10)
        if v_scale is None:
            v_scale = random.uniform(0.8, 1.2)
        if h_scale is None:
            h_scale = random.uniform(0.8, 1.2)
        
        # 基本参数
        bay_width = 4.0  # m
        story_height = 3.5  # m

        # 材料、截面参数
        Ec = 30000000.0
        Eb = 30000000.0
        Ac_ext = 0.16
        Ac_int = 0.20
        Ic_ext = 0.0053
        Ic_int = 0.0067
        Ab = 0.12
        Ib = 0.004

        # 结点编号：每层有 (bays+1) 个结点；地面层为第 0 层
        def node_id(level: int, grid: int) -> int:
            return level * (bays + 1) + grid + 1

        lines = []
        a = lines.append

        a("# 多层框架结构（自动生成）")
        a(f"# {stories}层、{bays}跨；荷载工况 case {case_idx} (v={v_scale:.2f}, h={h_scale:.2f})")
        a("")
        a("wipe")
        a("")
        a("# 单位：kN, m, s")
        a("")
        a("# 创建模型")
        a("model basic -ndm 2 -ndf 3")
        a("")

        # 结点
        a("# 定义结点")
        for level in range(0, stories + 1):
            y = level * story_height
            if level == 0:
                a("# 首层（地面）")
            elif level == stories:
                a("# 屋面（顶层）")
            else:
                a(f"# 第{level}层")
            for grid in range(0, bays + 1):
                x = grid * bay_width
                a(f"node {node_id(level, grid):d}  {x:.1f}  {y:.1f}")
            a("")

        # 约束：底部节点 x、y 固定，转动自由
        a("# 约束条件（底部铰接，转动自由）")
        for grid in range(0, bays + 1):
            a(f"fix {node_id(0, grid)}  1 1 0")
        a("")

        # 质量（动力分析）：按层均布到同层各结点，仅在平动自由度 (Ux, Uy) 上赋值
        a("# 定义楼层质量（用于动力分析）")
        m_floor = 100.0 * v_scale  # 基准楼层质量，随竖向荷载比例缩放
        m_node = m_floor / float(bays + 1)
        for level in range(1, stories + 1):
            for grid in range(0, bays + 1):
                nid = node_id(level, grid)
                a(f"mass {nid}   {m_node:.6f} {m_node:.6f} 0.0")
        a("")

        # 材料参数
        a("# 构件材料与截面参数")
        a(f"set Ec {Ec}")
        a(f"set Eb {Eb}")
        a(f"set Ac_ext {Ac_ext}")
        a(f"set Ac_int {Ac_int}")
        a(f"set Ic_ext {Ic_ext}")
        a(f"set Ic_int {Ic_int}")
        a(f"set Ab {Ab}")
        a(f"set Ib {Ib}")
        a("")

        # 几何转换
        a("# 几何转换")
        a("geomTransf Linear 1")
        a("")

        # 元素编号递增
        ele_id = 1

        # 柱单元：各层之间竖向连接
        a("# 定义柱单元")
        for level in range(0, stories):
            for grid in range(0, bays + 1):
                n_i = node_id(level, grid)
                n_j = node_id(level + 1, grid)
                # 边柱用外柱参数，内部用内柱参数
                if grid in (0, bays):
                    a(f"element elasticBeamColumn {ele_id}  {n_i}  {n_j} $Ac_ext $Ec $Ic_ext 1")
                else:
                    a(f"element elasticBeamColumn {ele_id}  {n_i}  {n_j} $Ac_int $Ec $Ic_int 1")
                ele_id += 1
        a("")

        # 梁单元：每一层（不含地面层）水平方向相邻结点之间
        a("# 定义梁单元")
        for level in range(1, stories + 1):
            for grid in range(0, bays):
                n_i = node_id(level, grid)
                n_j = node_id(level, grid + 1)
                a(f"element elasticBeamColumn {ele_id} {n_i} {n_j} $Ab $Eb $Ib 1")
                ele_id += 1
        a("")

        # 竖向荷载（按层、按内外侧不同取值，乘以 v_scale）
        a("# 竖向荷载")
        a("pattern Plain 1 Linear {")
        for level in range(1, stories + 1):
            is_roof = (level == stories)
            for grid in range(0, bays + 1):
                nid = node_id(level, grid)
                is_edge = (grid in (0, bays))
                if is_roof:
                    base_load = 60.0 if is_edge else 90.0
                else:
                    base_load = 80.0 if is_edge else 120.0
                load_val = -base_load * v_scale
                a(f"    load {nid}   0.0 {load_val:.3f}  0.0")
            a("")
        a("}")
        a("")

        # 水平荷载（按层三角分布，乘以 h_scale）
        a("# 水平荷载（风/地震）")
        a("pattern Plain 2 Linear {")
        # 基于层号线性放大：下层 1.0，顶层 stories 倍
        for level in range(1, stories + 1):
            factor = level / stories
            # 取每层中间结点作为水平力施加点：若偶数跨，取偏左中点
            mid_grid = bays // 2
            nid = node_id(level, mid_grid)
            base_h = 20.0  # 与模板同量级
            h = base_h * factor * h_scale
            a(f"    load {nid}   {h:.3f}  0.0  0.0")
        a("}")
        a("")

        # 分析设置
        a("# 分析设置")
        a("system BandSPD")
        a("numberer Plain")
        a("constraints Plain")
        a("integrator LoadControl 1.0")
        a("algorithm Linear")
        a("analysis Static")
        a("")

        # 执行分析（无输出打印）
        a("# 执行分析")
        a("analyze 1")
        a("")

        # 模态分析与瑞利阻尼（2% 阻尼，基于第1与第3振型）
        a("# 模态分析与阻尼设置")
        a("set lambda [eigen 3]")
        a("set omega1 [expr sqrt([lindex $lambda 0])]")
        a("set omega3 [expr sqrt([lindex $lambda 2])]")
        a("set zeta 0.02")
        a("set a0   [expr 2.0*$zeta*$omega1*$omega3/($omega1+$omega3)]")
        a("set a1   [expr 2.0*$zeta/($omega1+$omega3)]")
        a("rayleigh $a0 $a1 0.0 0.0")
        a("")

        return "\n".join(lines) + "\n"
    
    def _generate_shearwall_tcl(self, stories: int = None, bays: int = None, 
                               case_idx: int = None, v_scale: float = None, 
                               h_scale: float = None) -> str:
        """生成剪力墙结构TCL - 基于参考/ShearWall.py"""
        # 随机参数（如果未提供）
        if stories is None:
            stories = random.randint(2, 6)
        if bays is None:
            bays = random.randint(2, 5)
        if case_idx is None:
            case_idx = random.randint(1, 10)
        if v_scale is None:
            v_scale = random.uniform(0.8, 1.2)
        if h_scale is None:
            h_scale = random.uniform(0.8, 1.2)
        
        # 基本几何参数
        bay_width = 4.0  # m
        story_height = 3.5  # m

        # 剪力墙等效线单元刚度（相对较大）
        Ec = 30000000.0
        Eb = 30000000.0
        Ac_wall = 0.80   # 远大于框架柱
        Ic_wall = 0.050
        Ab_rigid = 1.0   # 水平刚性连接（等效刚梁）
        Ib_rigid = 0.10

        # 结点编号：每层 (bays+1) 个结点；地面层为 0 层
        def node_id(level: int, grid: int) -> int:
            return level * (bays + 1) + grid + 1

        lines = []
        a = lines.append

        a("# 剪力墙结构（自动生成）")
        a(f"# {stories}层、{bays}跨；荷载工况 case {case_idx} (v={v_scale:.2f}, h={h_scale:.2f})")
        a("")
        a("wipe")
        a("")
        a("# 单位：kN, m, s")
        a("")
        a("# 创建模型")
        a("model basic -ndm 2 -ndf 3")
        a("")

        # 结点
        a("# 定义结点")
        for level in range(0, stories + 1):
            y = level * story_height
            if level == 0:
                a("# 首层（地面）")
            elif level == stories:
                a("# 屋面（顶层）")
            else:
                a(f"# 第{level}层")
            for grid in range(0, bays + 1):
                x = grid * bay_width
                a(f"node {node_id(level, grid):d}  {x:.1f}  {y:.1f}")
            a("")

        # 底部约束
        a("# 约束条件（底部铰接，转动自由）")
        for grid in range(0, bays + 1):
            a(f"fix {node_id(0, grid)}  1 1 0")
        a("")

        # 楼层质量（动力分析），分配到同层所有结点（Ux, Uy 均赋值）
        a("# 定义楼层质量（用于动力分析）")
        m_floor = 120.0 * v_scale
        m_node = m_floor / float(bays + 1)
        for level in range(1, stories + 1):
            for grid in range(0, bays + 1):
                nid = node_id(level, grid)
                a(f"mass {nid}   {m_node:.6f} {m_node:.6f} 0.0")
        a("")

        # 材料与几何转换
        a("# 材料与几何转换")
        a(f"set Ec {Ec}")
        a(f"set Eb {Eb}")
        a(f"set Ac_wall {Ac_wall}")
        a(f"set Ic_wall {Ic_wall}")
        a(f"set Ab_rigid {Ab_rigid}")
        a(f"set Ib_rigid {Ib_rigid}")
        a("geomTransf Linear 1")
        a("")

        # 元素定义：仅边墙（左、右）作为竖向受力构件；楼层采用刚性楼板约束（equalDOF）
        a("# 定义边墙（竖向）")
        ele_id = 1
        for level in range(0, stories):
            for grid in (0, bays):
                n_i = node_id(level, grid)
                n_j = node_id(level + 1, grid)
                a(f"element elasticBeamColumn {ele_id}  {n_i}  {n_j} $Ac_wall $Ec $Ic_wall 1")
                ele_id += 1
        a("")

        # 刚性楼板：将同层所有结点的 Ux 约束为与主结点一致
        a("# 刚性楼板约束")
        for level in range(1, stories + 1):
            master = node_id(level, 0)
            for grid in range(1, bays + 1):
                slave = node_id(level, grid)
                a(f"equalDOF {master} {slave} 1")
        a("")

        # 荷载
        a("# 竖向荷载")
        a("pattern Plain 1 Linear {")
        for level in range(1, stories + 1):
            is_roof = (level == stories)
            for grid in range(0, bays + 1):
                nid = node_id(level, grid)
                base = 60.0 if is_roof else 100.0
                a(f"    load {nid}   0.0 {-base * v_scale:.3f}  0.0")
            a("")
        a("}")
        a("")

        a("# 水平荷载（随层高线性增大，施加于主结点）")
        a("pattern Plain 2 Linear {")
        for level in range(1, stories + 1):
            factor = level / stories
            master = node_id(level, 0)
            base_h = 30.0
            a(f"    load {master}   {base_h * factor * h_scale:.3f}  0.0  0.0")
        a("}")
        a("")

        # 分析
        a("# 分析设置")
        a("system BandSPD")
        a("numberer Plain")
        a("constraints Plain")
        a("integrator LoadControl 1.0")
        a("algorithm Linear")
        a("analysis Static")
        a("")
        a("# 执行分析（不打印结果）")
        a("analyze 1")
        a("")

        # 模态与阻尼
        a("# 模态分析与阻尼设置")
        a("set lambda [eigen 3]")
        a("set omega1 [expr sqrt([lindex $lambda 0])]")
        a("set omega3 [expr sqrt([lindex $lambda 2])]")
        a("set zeta 0.02")
        a("set a0   [expr 2.0*$zeta*$omega1*$omega3/($omega1+$omega3)]")
        a("set a1   [expr 2.0*$zeta/($omega1+$omega3)]")
        a("rayleigh $a0 $a1 0.0 0.0")
        a("")

        return "\n".join(lines) + "\n"
    
    def _generate_frame_shearwall_tcl(self, stories: int = None, bays: int = None, 
                                     case_idx: int = None, v_scale: float = None, 
                                     h_scale: float = None) -> str:
        """生成框架剪力墙结构TCL - 基于参考/FrameShearWall.py"""
        # 随机参数（如果未提供）
        if stories is None:
            stories = random.randint(2, 6)
        if bays is None:
            bays = random.randint(2, 5)
        if case_idx is None:
            case_idx = random.randint(1, 10)
        if v_scale is None:
            v_scale = random.uniform(0.8, 1.2)
        if h_scale is None:
            h_scale = random.uniform(0.8, 1.2)
        
        # 基本参数
        bay_width = 4.0
        story_height = 3.5

        # 框架与墙参数（墙刚度更大）
        Ec = 30000000.0
        Eb = 30000000.0
        Ac_ext = 0.16
        Ac_int = 0.20
        Ic_ext = 0.0053
        Ic_int = 0.0067
        Ab = 0.12
        Ib = 0.004

        Ac_wall = 0.80
        Ic_wall = 0.050

        def node_id(level: int, grid: int) -> int:
            return level * (bays + 1) + grid + 1

        lines = []
        a = lines.append

        a("# 框架-剪力墙结构（自动生成）")
        a(f"# {stories}层、{bays}跨；荷载工况 case {case_idx} (v={v_scale:.2f}, h={h_scale:.2f})")
        a("")
        a("wipe")
        a("")
        a("# 单位：kN, m, s")
        a("")
        a("# 创建模型")
        a("model basic -ndm 2 -ndf 3")
        a("")

        # 结点
        a("# 定义结点")
        for level in range(0, stories + 1):
            y = level * story_height
            if level == 0:
                a("# 首层（地面）")
            elif level == stories:
                a("# 屋面（顶层）")
            else:
                a(f"# 第{level}层")
            for grid in range(0, bays + 1):
                x = grid * bay_width
                a(f"node {node_id(level, grid):d}  {x:.1f}  {y:.1f}")
            a("")

        # 底部约束
        a("# 约束条件（底部铰接，转动自由）")
        for grid in range(0, bays + 1):
            a(f"fix {node_id(0, grid)}  1 1 0")
        a("")

        # 楼层质量
        a("# 定义楼层质量（用于动力分析）")
        m_floor = 110.0 * v_scale
        m_node = m_floor / float(bays + 1)
        for level in range(1, stories + 1):
            for grid in range(0, bays + 1):
                nid = node_id(level, grid)
                a(f"mass {nid}   {m_node:.6f} {m_node:.6f} 0.0")
        a("")

        # 材料参数与几何转换
        a("# 材料与几何转换")
        a(f"set Ec {Ec}")
        a(f"set Eb {Eb}")
        a(f"set Ac_ext {Ac_ext}")
        a(f"set Ac_int {Ac_int}")
        a(f"set Ic_ext {Ic_ext}")
        a(f"set Ic_int {Ic_int}")
        a(f"set Ab {Ab}")
        a(f"set Ib {Ib}")
        a(f"set Ac_wall {Ac_wall}")
        a(f"set Ic_wall {Ic_wall}")
        a("geomTransf Linear 1")
        a("")

        # 元素：边跨为剪力墙，中间为框架柱；水平为框架梁
        a("# 定义柱/墙单元（边墙+内柱）")
        ele_id = 1
        for level in range(0, stories):
            for grid in range(0, bays + 1):
                n_i = node_id(level, grid)
                n_j = node_id(level + 1, grid)
                if grid in (0, bays):
                    # 边柱替换为剪力墙
                    a(f"element elasticBeamColumn {ele_id}  {n_i}  {n_j} $Ac_wall $Ec $Ic_wall 1")
                else:
                    # 中间为框架柱（内柱参数）
                    a(f"element elasticBeamColumn {ele_id}  {n_i}  {n_j} $Ac_int $Ec $Ic_int 1")
                ele_id += 1
        a("")

        a("# 定义梁单元（所有跨为框架梁）")
        for level in range(1, stories + 1):
            for grid in range(0, bays):
                n_i = node_id(level, grid)
                n_j = node_id(level, grid + 1)
                a(f"element elasticBeamColumn {ele_id} {n_i} {n_j} $Ab $Eb $Ib 1")
                ele_id += 1
        a("")

        # 楼层刚性约束（equalDOF，仅约束 Ux，使楼层形成整体侧移）
        a("# 刚性楼板约束")
        for level in range(1, stories + 1):
            master = node_id(level, 0)
            for grid in range(1, bays + 1):
                slave = node_id(level, grid)
                a(f"equalDOF {master} {slave} 1")
        a("")

        # 荷载
        a("# 竖向荷载")
        a("pattern Plain 1 Linear {")
        for level in range(1, stories + 1):
            is_roof = (level == stories)
            for grid in range(0, bays + 1):
                nid = node_id(level, grid)
                if is_roof:
                    base = 60.0 if grid in (0, bays) else 90.0
                else:
                    base = 80.0 if grid in (0, bays) else 120.0
                a(f"    load {nid}   0.0 {-base * v_scale:.3f}  0.0")
            a("")
        a("}")
        a("")

        a("# 水平荷载（施加于主结点，与楼板约束一致）")
        a("pattern Plain 2 Linear {")
        for level in range(1, stories + 1):
            factor = level / stories
            master = node_id(level, 0)
            base_h = 25.0
            a(f"    load {master}   {base_h * factor * h_scale:.3f}  0.0  0.0")
        a("}")
        a("")

        # 分析
        a("# 分析设置")
        a("system BandSPD")
        a("numberer Plain")
        a("constraints Plain")
        a("integrator LoadControl 1.0")
        a("algorithm Linear")
        a("analysis Static")
        a("")
        a("# 执行分析（不打印结果）")
        a("analyze 1")
        a("")

        # 模态与阻尼
        a("# 模态分析与阻尼设置")
        a("set lambda [eigen 3]")
        a("set omega1 [expr sqrt([lindex $lambda 0])]")
        a("set omega3 [expr sqrt([lindex $lambda 2])]")
        a("set zeta 0.02")
        a("set a0   [expr 2.0*$zeta*$omega1*$omega3/($omega1+$omega3)]")
        a("set a1   [expr 2.0*$zeta/($omega1+$omega3)]")
        a("rayleigh $a0 $a1 0.0 0.0")
        a("")

        return "\n".join(lines) + "\n"


def main():
    """测试函数"""
    print("=== 结构预处理器测试 ===")
    
    preprocessor = StructurePreprocessor()
    
    # 测试三种结构类型
    structure_types = ["框架", "剪力墙", "框架剪力墙"]
    
    for structure_type in structure_types:
        print(f"\n生成 {structure_type} 结构TCL:")
        tcl_content = preprocessor.generate_tcl(structure_type)
        print(f"TCL内容长度: {len(tcl_content)} 字符")
        print("前200字符预览:")
        print(tcl_content[:200] + "...")


if __name__ == "__main__":
    main()