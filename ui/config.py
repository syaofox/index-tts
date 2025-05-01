"""配置常量模块
存储应用程序中共享的常量配置。
"""

# 文件路径常量
REPLACE_RULES_CONFIG_PATH = "ui/text_replace_config.txt" 

# 音频播放器路径配置
# 留空则使用系统默认播放器，否则使用指定的播放器程序
# 如果是Adobe Audition，请确保路径正确
AUDIO_PLAYER_PATH = "C:/Program Files/Adobe/Adobe Audition 2023/Adobe Audition.exe" 

# 语音生成默认配置
DEFAULT_PUNCT_CHARS = "。？！；.?!."  # 默认分割标点符号
DEFAULT_PAUSE_TIME = "0.3"     # 默认停顿时间(秒) 