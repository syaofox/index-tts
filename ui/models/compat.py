"""类型兼容性模块
为不同Python版本提供类型注解兼容性。
"""

# 添加Self类型的兼容性支持
try:
    from typing import Self
except ImportError:
    try:
        from typing_extensions import Self
    except ImportError:
        # 如果无法导入，我们定义一个假的Self类型
        Self = object 