import os
import subprocess
from typing import Optional


class EnvironmentManager:
    """管理OpenSees虚拟环境和Python环境"""
    
    def __init__(self, venv_dir: str = "./opensees_venv", status_callback=None):
        self.venv_dir = venv_dir
        self.status_callback = status_callback or print

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

    def _get_venv_python_path(self) -> Optional[str]:
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
            if not python_path:
                raise Exception("无法获取虚拟环境Python路径")
            
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

