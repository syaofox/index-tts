"""IndexTTS Python API
"""

# 添加类型兼容层
try:
    from typing import Self
except ImportError:
    try:
        from typing_extensions import Self
    except ImportError:
        # 如果无法导入，我们定义一个假的Self类型
        Self = object

from indextts.cli import main
from indextts.infer import IndexTTS

__version__ = "0.1.0"
