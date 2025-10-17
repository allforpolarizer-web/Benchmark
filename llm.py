#!/usr/bin/env python3
import os
import json
import subprocess
import requests
import time
import re
from typing import Dict, Optional, Any

# HTTP/HTTPS 代理
os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7890")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")


class OpenSeesSingleTurnAgent:
    def __init__(self, api_key: Optional[str] = None, temp_dir: str = "./temp_opensees", auto_setup: bool = True, status_callback=None):
        """简化的OpenSees Agent - 工作流模式"""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("需要设置GEMINI_API_KEY环境变量")

        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        }

        self.temp_dir = temp_dir
        self.venv_dir = "./opensees_venv"
        self.status_callback = status_callback or print
        os.makedirs(temp_dir, exist_ok=True)

        # 自动设置虚拟环境
        if auto_setup:
            self.setup_environment()

    def setup_environment(self):
        """设置虚拟环境和必要包 - 云部署友好版本"""
        self.status_callback("🔧 检查OpenSees环境...")

        # 首先检查是否已有可用的openseespy环境
        if self._find_working_openseespy_environment():
            self.status_callback("✅ 发现可用的openseespy环境，跳过虚拟环境创建")
            return

        # 检查虚拟环境是否存在
        if os.path.exists(self.venv_dir):
            self.status_callback(f"✅ 虚拟环境已存在: {self.venv_dir}")
            # 测试虚拟环境中的openseespy
            venv_python = self._get_venv_python_path()
            if venv_python and self._test_openseespy_compatibility(venv_python):
                self.status_callback("✅ 虚拟环境中openseespy可用")
                return
            else:
                self.status_callback("⚠️  虚拟环境中openseespy不可用，尝试重新安装...")

        self._create_virtual_environment()

    def _find_working_openseespy_environment(self) -> bool:
        """查找已有的可用openseespy环境"""
        python_candidates = [
            'python',      # conda/miniconda/pyenv
            'python3',     # 系统Python3
        ]

        for python_exe in python_candidates:
            if self._test_openseespy_compatibility(python_exe):
                self.status_callback(f"✅ 发现可用环境: {python_exe}")
                return True
        return False

    def _get_venv_python_path(self) -> str:
        """获取虚拟环境Python路径"""
        if os.name == 'nt':  # Windows
            return os.path.join(self.venv_dir, 'Scripts', 'python.exe')
        else:  # Unix/Linux/Mac
            return os.path.join(self.venv_dir, 'bin', 'python')

    def _create_virtual_environment(self):
        """创建虚拟环境"""
        self.status_callback(f"📦 创建虚拟环境: {self.venv_dir}")

        try:
            # 尝试多种Python命令创建虚拟环境
            python_commands = ['python3', 'python']

            for python_cmd in python_commands:
                try:
                    subprocess.run([
                        python_cmd, '-m', 'venv', self.venv_dir
                    ], check=True, capture_output=True)
                    self.status_callback("✅ 虚拟环境创建成功")
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            else:
                raise Exception("无法找到可用的Python命令创建虚拟环境")

            # 获取虚拟环境的python路径
            python_path = self._get_venv_python_path()
            pip_path = os.path.join(os.path.dirname(python_path), 'pip')

            # 升级pip
            self.status_callback("⬆️  升级pip...")
            subprocess.run([
                python_path, '-m', 'pip', 'install', '--upgrade', 'pip'
            ], check=True, capture_output=True)

            # 尝试多种方式安装openseespy
            self._install_openseespy_packages(python_path, pip_path)

            self.status_callback("✅ 环境设置完成！")
            self._create_usage_file()

        except subprocess.CalledProcessError as e:
            self.status_callback(f"❌ 环境设置失败: {e}")
            self.status_callback("将使用系统默认Python环境")
        except Exception as e:
            self.status_callback(f"❌ 环境设置异常: {e}")
            self.status_callback("将使用系统默认Python环境")

    def _install_openseespy_packages(self, python_path: str, pip_path: str):
        """尝试多种方式安装openseespy"""
        packages = ['numpy', 'matplotlib', 'scipy']  # 基础包

        # 安装基础包
        self.status_callback("📥 安装基础包...")
        for package in packages:
            try:
                subprocess.run([
                    pip_path, 'install', package
                ], check=True, capture_output=True)
                self.status_callback(f"    ✅ {package} 安装成功")
            except subprocess.CalledProcessError:
                self.status_callback(f"    ⚠️  {package} 安装失败，但继续执行...")

        # 尝试安装openseespy
        self.status_callback("📥 尝试安装openseespy...")
        opensees_install_methods = [
            # 方法1: 标准pip安装
            [pip_path, 'install', 'openseespy'],
            # 方法2: 强制重新安装
            [pip_path, 'install', '--force-reinstall', '--no-cache-dir', 'openseespy'],
            # 方法3: 指定索引
            [pip_path, 'install', '-i', 'https://pypi.org/simple/', 'openseespy'],
        ]

        for method in opensees_install_methods:
            try:
                subprocess.run(method, check=True, capture_output=True)
                # 测试安装是否成功
                if self._test_openseespy_compatibility(python_path):
                    self.status_callback("✅ openseespy安装并测试成功")
                    return
                else:
                    self.status_callback("⚠️  openseespy安装成功但测试失败，尝试下一种方法...")
            except subprocess.CalledProcessError:
                self.status_callback("⚠️  当前安装方法失败，尝试下一种...")
                continue

        self.status_callback("⚠️  所有openseespy安装方法都失败，将依赖subprocess fallback")

    def _create_usage_file(self):
        """创建使用说明文件"""
        usage_file = os.path.join(self.venv_dir, "README.txt")
        with open(usage_file, 'w', encoding='utf-8') as f:
            f.write("""OpenSees虚拟环境使用说明

激活虚拟环境:
  Linux/Mac: source opensees_venv/bin/activate
  Windows:   opensees_venv\\Scripts\\activate.bat

在虚拟环境中使用Python:
  ./opensees_venv/bin/python  (Linux/Mac)
  .\\opensees_venv\\Scripts\\python.exe  (Windows)

已安装的包:
  - openseespy: OpenSees的Python接口(如果兼容)
  - numpy: 数值计算
  - matplotlib: 绘图
  - scipy: 科学计算

注意:
- 系统会自动检测最兼容的Python环境
- 如果openseespy不兼容，会自动fallback到subprocess调用
- 云部署时请确保OpenSees可执行文件在PATH中
""")

    def get_python_executable(self) -> str:
        """获取要使用的Python可执行文件路径 - 自适应选择最佳环境"""

        # 优先级1: 检查虚拟环境
        if os.path.exists(self.venv_dir):
            if os.name == 'nt':  # Windows
                venv_python = os.path.join(self.venv_dir, 'Scripts', 'python.exe')
            else:  # Unix/Linux/Mac
                venv_python = os.path.join(self.venv_dir, 'bin', 'python')

            if os.path.exists(venv_python):
                # 测试虚拟环境中的openseespy是否可用
                if self._test_openseespy_compatibility(venv_python):
                    return venv_python
                else:
                    print(f"⚠️  虚拟环境Python不兼容openseespy，寻找替代方案...")

        # 优先级2: 测试各种Python环境的openseespy兼容性
        python_candidates = [
            'python',      # 可能是conda/miniconda
            'python3',     # 系统Python3
            '/usr/bin/python3',  # 系统默认Python3
            '/opt/homebrew/bin/python3',  # Homebrew Python (ARM64 Mac)
            '/usr/local/bin/python3',     # Homebrew Python (Intel Mac)
        ]

        for python_exe in python_candidates:
            if self._test_openseespy_compatibility(python_exe):
                print(f"✅ 找到兼容的Python环境: {python_exe}")
                return python_exe

        # 优先级3: 回退到系统Python（即使openseespy不可用）
        print("⚠️  未找到openseespy兼容环境，使用系统Python（将依赖subprocess fallback）")
        return 'python3'

    def _test_openseespy_compatibility(self, python_exe: str) -> bool:
        """测试指定Python环境中openseespy的兼容性"""
        try:
            # 快速测试openseespy导入和基本操作
            test_cmd = [
                python_exe, '-c',
                'import openseespy.opensees as ops; ops.wipe(); print("OK")'
            ]

            result = subprocess.run(
                test_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            return result.returncode == 0 and "OK" in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    def read_tcl_file(self, tcl_path: str) -> tuple[bool, str]:
        """读取TCL文件"""
        try:
            with open(tcl_path, 'r', encoding='utf-8') as f:
                return True, f.read()
        except FileNotFoundError:
            return False, f"文件不存在: {tcl_path}"
        except PermissionError:
            return False, f"权限不足: {tcl_path}"
        except UnicodeDecodeError as e:
            return False, f"编码错误: {tcl_path} - {e}"
        except Exception as e:
            return False, f"读取失败: {tcl_path} - {type(e).__name__}: {str(e)}"

    def call_gemini(self, prompt: str) -> Optional[str]:
        """调用Gemini API"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 20000}
        }

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                print(data)
                if 'candidates' in data and data['candidates']:
                    content = data['candidates'][0]['content']
                    if 'parts' in content and content['parts']:
                        return content['parts'][0]['text']
                    elif 'text' in content:
                        return content['text']
                else:
                    print(f"❌ Gemini API响应无候选结果: {data}")
            else:
                print(f"❌ Gemini API错误: {response.status_code} - {response.text}")
            return None
        except requests.exceptions.Timeout:
            print("❌ Gemini API超时")
            return None
        except requests.exceptions.ConnectionError:
            print("❌ Gemini API连接失败")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Gemini API请求异常: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            print(f"❌ Gemini API未知错误: {type(e).__name__}: {e}")
            return None

    def extract_python_code(self, text: str) -> str:
        """提取Python代码"""
        patterns = [
            r'```python\s*\n([\s\S]*?)\n```',
            r'```\s*\n([\s\S]*?)\n```'
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return max(matches, key=len).strip()

        # 如果没有找到代码块，检查是否整个文本以```python开头
        text = text.strip()
        if text.startswith('```python'):
            lines = text.split('\n')
            # 移除第一行的```python
            lines = lines[1:]
            # 移除最后一行的```（如果存在）
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            return '\n'.join(lines).strip()
        elif text.startswith('```'):
            lines = text.split('\n')
            # 移除第一行的```
            lines = lines[1:]
            # 移除最后一行的```（如果存在）
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            return '\n'.join(lines).strip()

        return text.strip()

    def process_single_turn(self, tcl_file_path: str, user_command: str) -> Dict[str, Any]:
        """执行6步工作流：think, code, extract_code, write, exec, return_result"""
        self.status_callback("🚀 OpenSees 工作流模式 - 6步骤执行")

        result = {
            "success": False,
            "tcl_file_path": tcl_file_path,
            "user_command": user_command,
            "think_response": "",
            "code_response": "",
            "extracted_code": "",
            "temp_file_path": "",
            "execution_result": {},
            "errors": [],
            "failed_steps": []
        }

        # 步骤1: Think
        self.status_callback("🧠 正在思考分析方案...")
        if not self._step_think(tcl_file_path, user_command, result):
            result["failed_steps"].append("think")
            self.status_callback("⚠️ Think步骤失败，但继续执行...")

        # 步骤2: Code
        self.status_callback("💻 正在生成Python代码...")
        if not self._step_code(result):
            result["failed_steps"].append("code")
            self.status_callback("⚠️ Code步骤失败，但继续执行...")

        # 步骤3: Extract Code (只有Code成功才执行)
        self.status_callback("📝 正在提取代码...")
        if "code" not in result["failed_steps"]:
            if not self._step_extract_code(result):
                result["failed_steps"].append("extract_code")
                self.status_callback("⚠️ Extract步骤失败，但继续执行...")
        else:
            self.status_callback("⏭️ 跳过Extract步骤 (Code步骤失败)")
            result["failed_steps"].append("extract_code")

        # 步骤4: Write (只有Extract成功才执行)
        self.status_callback("✍️ 正在写入临时文件...")
        if "extract_code" not in result["failed_steps"]:
            if not self._step_write(result):
                result["failed_steps"].append("write")
                self.status_callback("⚠️ Write步骤失败，但继续执行...")
        else:
            self.status_callback("⏭️ 跳过Write步骤 (Extract步骤失败)")
            result["failed_steps"].append("write")

        # 步骤5: Exec (只有Write成功才执行)
        self.status_callback("🚀 正在执行代码...")
        if "write" not in result["failed_steps"]:
            if not self._step_exec(result):
                result["failed_steps"].append("exec")
                self.status_callback("❌ Exec步骤失败")
            else:
                self.status_callback("✅ Exec步骤成功")
        else:
            self.status_callback("⏭️ 跳过Exec步骤 (Write步骤失败)")
            result["failed_steps"].append("exec")

        # 步骤6: Return Result
        self.status_callback("📋 返回结果...")
        # 如果没有关键步骤失败，认为整体成功
        critical_failures = [step for step in result["failed_steps"] if step in ["think", "code", "extract_code", "write"]]
        result["success"] = len(critical_failures) == 0 and "exec" not in result["failed_steps"]

        if result["success"]:
            self.status_callback("✅ 工作流完成")
        else:
            self.status_callback(f"⚠️ 工作流部分失败 (失败步骤: {', '.join(result['failed_steps'])})")

        return result

    def _step_think(self, tcl_file_path: str, user_command: str, result: Dict[str, Any]) -> bool:
        success, tcl_content = self.read_tcl_file(tcl_file_path)
        if not success:
            result["errors"].append(f"步骤1失败 - {tcl_content}")
            self.status_callback(f"❌ {tcl_content}")
            return False

        prompt = f"""
分析OpenSees任务：

TCL文件：
{tcl_content}

用户指令：{user_command}

请简要分析用户需求, 思考下一步如何撰写代码, 这里仅仅思考用户意图和思路，不要写出代码，尽量精简。
Keep it simple and stupid.
        """

        response = self.call_gemini(prompt)
        if not response:
            result["errors"].append("步骤1失败 - Gemini API调用失败")
            self.status_callback("❌ Think步骤: Gemini API无响应")
            return False

        result["think_response"] = response
        result["tcl_content"] = tcl_content
        self.status_callback("✅ Think完成")
        return True

    def _step_code(self, result: Dict[str, Any]) -> bool:
        prompt = f"""
你是一个openseespy专家。根据TCL文件内容生成Python代码。

分析：{result["think_response"]}
指令：{result["user_command"]}

TCL文件内容：
{result["tcl_content"]}

生成完整Python代码，用```python 和 ``` 包围。

【严格要求】：
1. ❌ 禁止使用 ops.source() - 这个方法不存在！
2. ❌ 禁止尝试读取或执行TCL文件
3. ✅ 必须根据TCL内容手动转换每一行命令
4. ✅ 变量必须明确定义，避免作用域问题

【转换规则】：
```
# TCL → Python 精确映射
wipe → ops.wipe()
model basic -ndm 2 -ndf 3 → ops.model('basic', '-ndm', 2, '-ndf', 3)
node 1 0.0 0.0 → ops.node(1, 0.0, 0.0)
node 2 5.0 0.0 → ops.node(2, 5.0, 0.0)
node 3 10.0 0.0 → ops.node(3, 10.0, 0.0)
fix 1 1 1 1 → ops.fix(1, 1, 1, 1)
fix 3 0 1 0 → ops.fix(3, 0, 1, 0)
uniaxialMaterial Elastic 1 200000.0 → ops.uniaxialMaterial('Elastic', 1, 200000.0)
section Elastic 1 200000.0 2000.0 1000000.0 → ops.section('Elastic', 1, 200000.0, 2000.0, 1000000.0)
geomTransf Linear 1 → ops.geomTransf('Linear', 1)
element elasticBeamColumn 1 1 2 2000.0 200000.0 1000000.0 1 → ops.element('elasticBeamColumn', 1, 1, 2, 2000.0, 200000.0, 1000000.0, 1)
pattern Plain 1 Linear {{}} → ops.timeSeries('Linear', 1); ops.pattern('Plain', 1, 1)
load 2 0.0 -50.0 0.0 → ops.load(2, 0.0, -50.0, 0.0)
constraints Plain → ops.constraints('Plain')
numberer RCM → ops.numberer('RCM')
system BandSPD → ops.system('BandSPD')
test NormDispIncr 1.0e-6 6 → ops.test('NormDispIncr', 1.0e-6, 6)
algorithm Newton → ops.algorithm('Newton')
integrator LoadControl 1.0 → ops.integrator('LoadControl', 1.0)
analysis Static → ops.analysis('Static')
analyze 1 → ops.analyze(1)
```

【强制模板】：
请严格按照以下模板生成代码，不要偏离：

```python
import openseespy.opensees as ops

# 1. 清理
ops.wipe()

# 2. 模型定义 (根据TCL的model命令)
ops.model('basic', '-ndm', 2, '-ndf', 3)

# 3. 节点 (根据TCL的node命令逐个添加)
ops.node(1, 0.0, 0.0)
ops.node(2, 5.0, 0.0)
ops.node(3, 10.0, 0.0)

# 4. 边界条件 (根据TCL的fix命令)
ops.fix(1, 1, 1, 1)
ops.fix(3, 0, 1, 0)

# 5. 材料 (根据TCL的uniaxialMaterial命令)
ops.uniaxialMaterial('Elastic', 1, 200000.0)

# 6. 截面 (根据TCL的section命令)
ops.section('Elastic', 1, 200000.0, 2000.0, 1000000.0)

# 7. 几何变换 (根据TCL的geomTransf命令)
ops.geomTransf('Linear', 1)

# 8. 单元 (根据TCL的element命令)
ops.element('elasticBeamColumn', 1, 1, 2, 2000.0, 200000.0, 1000000.0, 1)
ops.element('elasticBeamColumn', 2, 2, 3, 2000.0, 200000.0, 1000000.0, 1)

# 9. 荷载 (根据TCL的pattern和load命令)
ops.timeSeries('Linear', 1)
ops.pattern('Plain', 1, 1)
ops.load(2, 0.0, -50.0, 0.0)

# 10. 分析设置 (根据TCL的constraints等命令)
ops.constraints('Plain')
ops.numberer('RCM')
ops.system('BandSPD')
ops.test('NormDispIncr', 1.0e-6, 6)
ops.algorithm('Newton')
ops.integrator('LoadControl', 1.0)
ops.analysis('Static')

# 11. 执行分析
result = ops.analyze(1)
if result == 0:
    print("分析成功完成")
else:
    print("分析失败")
```

请严格按照以上模板，根据给定的TCL文件内容填入正确的参数值。
        """

        response = self.call_gemini(prompt)
        if not response:
            result["errors"].append("步骤2失败 - Gemini API调用失败")
            self.status_callback("❌ Code步骤: Gemini API无响应")
            return False

        result["code_response"] = response
        self.status_callback("✅ Code完成")
        return True

    def _step_extract_code(self, result: Dict[str, Any]) -> bool:
        code = self.extract_python_code(result["code_response"])
        if not code.strip():
            result["errors"].append("步骤3失败 - 未找到有效Python代码")
            self.status_callback("❌ Extract步骤: 代码提取为空")
            return False
        result["extracted_code"] = code
        self.status_callback(f"✅ Extract完成: {len(code)}字符")
        return True

    def _step_write(self, result: Dict[str, Any]) -> bool:
        timestamp = int(time.time())
        temp_file = os.path.join(self.temp_dir, f"opensees_{timestamp}.py")

        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(result["extracted_code"])
            result["temp_file_path"] = temp_file
            self.status_callback(f"✅ Write完成: {temp_file}")
            return True
        except PermissionError:
            error_msg = f"步骤4失败 - 权限不足: {temp_file}"
            result["errors"].append(error_msg)
            self.status_callback(f"❌ {error_msg}")
            return False
        except OSError as e:
            error_msg = f"步骤4失败 - 文件系统错误: {e}"
            result["errors"].append(error_msg)
            self.status_callback(f"❌ {error_msg}")
            return False
        except Exception as e:
            error_msg = f"步骤4失败 - {type(e).__name__}: {e}"
            result["errors"].append(error_msg)
            self.status_callback(f"❌ {error_msg}")
            return False

    def _step_exec(self, result: Dict[str, Any]) -> bool:
        python_executable = self.get_python_executable()
        try:
            proc = subprocess.run(
                [python_executable, result["temp_file_path"]],
                capture_output=True,
                text=True,
                timeout=120
            )

            result["execution_result"] = {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "return_code": proc.returncode,
                "python_used": python_executable
            }

            if proc.returncode == 0:
                self.status_callback("✅ Exec完成")
                return True
            else:
                error_msg = f"步骤5失败 - 代码执行错误(返回码:{proc.returncode}): {proc.stderr.strip() or 'No stderr output'}"
                result["errors"].append(error_msg)
                self.status_callback(f"❌ {error_msg}")
                return False

        except subprocess.TimeoutExpired:
            error_msg = "步骤5失败 - 代码执行超时(120秒)"
            result["errors"].append(error_msg)
            self.status_callback(f"❌ {error_msg}")
            return False
        except FileNotFoundError:
            error_msg = f"步骤5失败 - {python_executable}命令未找到"
            result["errors"].append(error_msg)
            self.status_callback(f"❌ {error_msg}")
            return False
        except Exception as e:
            error_msg = f"步骤5失败 - {type(e).__name__}: {e}"
            result["errors"].append(error_msg)
            self.status_callback(f"❌ {error_msg}")
            return False

    def format_result(self, result: Dict[str, Any]) -> str:
        """格式化结果"""
        output = ["=" * 60, "OpenSees 工作流结果", "=" * 60]

        output.append(f"\n📁 文件: {result['tcl_file_path']}")
        output.append(f"💬 指令: {result['user_command']}")
        output.append(f"✅ 状态: {'成功' if result['success'] else '失败'}")

        if result.get('failed_steps'):
            output.append(f"\n⚠️  失败步骤: {', '.join(result['failed_steps'])}")

        if result.get('errors'):
            output.append(f"\n❌ 错误:")
            for error in result['errors']:
                output.append(f"  - {error}")

        if result.get('think_response'):
            output.append(f"\n🧠 Think: {result['think_response'][:500]}...")

        if result.get('extracted_code'):
            output.append(f"\n💻 Code: {result['extracted_code'][:500]}...")

        if result.get('execution_result'):
            exec_res = result['execution_result']
            output.append(f"\n🔄 执行: {'成功' if exec_res.get('success') else '失败'}")
            if exec_res.get('stdout'):
                output.append(f"输出: {exec_res['stdout']}")

        output.append("\n" + "=" * 60)
        return '\n'.join(output)

    def cleanup_temp_files(self, keep_latest: int = 5):
        """清理临时文件"""
        try:
            files = [(f, os.path.getctime(os.path.join(self.temp_dir, f)))
                    for f in os.listdir(self.temp_dir)
                    if f.startswith("opensees_") and f.endswith(".py")]

            files.sort(key=lambda x: x[1], reverse=True)
            for file, _ in files[keep_latest:]:
                os.remove(os.path.join(self.temp_dir, file))
        except:
            pass


def main():
    """主函数"""
    import sys

    print("=== OpenSees 工作流模式Agent ===")

    if len(sys.argv) < 3:
        print("\n使用方法:")
        print("python opensees_single_turn_agent.py <tcl_file> <命令>")
        print("\n示例:")
        print('python opensees_single_turn_agent.py simple.tcl "添加荷载分析"')
        print("\n工作流步骤:")
        print("1. Think - 2. Code - 3. Extract - 4. Write - 5. Exec - 6. Result")
        sys.exit(1)

    tcl_file_path = sys.argv[1]
    user_command = ' '.join(sys.argv[2:])

    try:
        agent = OpenSeesSingleTurnAgent()
        result = agent.process_single_turn(tcl_file_path, user_command)
        print(agent.format_result(result))
        agent.cleanup_temp_files()

        # 如果有Exec成功，或者只有非关键步骤失败，返回0
        if result['success'] or (result.get('execution_result', {}).get('success')):
            sys.exit(0)
        else:
            sys.exit(1)

    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        print("设置: export GEMINI_API_KEY='your-key'")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()