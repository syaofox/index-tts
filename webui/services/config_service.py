import os
import json
from webui.utils.logger import info, error


class ConfigService:
    """配置管理服务，用于保存和加载应用配置"""

    def __init__(self, config_file="webui/config.json"):
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self):
        """加载配置文件，如果不存在则创建默认配置"""
        if not os.path.exists(self.config_file):
            # 默认配置
            default_config = {
                "audio_settings": {"silence_duration": 0.3, "scale_rate": 1.0}
            }
            return default_config

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                info(f"已加载配置文件: {self.config_file}")
                return config
        except Exception as e:
            error(f"加载配置文件失败: {str(e)}")
            # 返回默认配置
            return {"audio_settings": {"silence_duration": 0.3, "scale_rate": 1.0}}

    def save_config(self):
        """保存配置到文件"""
        try:
            # 确保配置文件目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            info(f"配置已保存到: {self.config_file}")
            return True
        except Exception as e:
            error(f"保存配置文件失败: {str(e)}")
            return False

    def get_audio_settings(self):
        """获取音频设置"""
        return self.config.get(
            "audio_settings", {"silence_duration": 0.3, "scale_rate": 1.0}
        )

    def save_audio_settings(self, silence_duration, scale_rate):
        """保存音频设置"""
        self.config["audio_settings"] = {
            "silence_duration": silence_duration,
            "scale_rate": scale_rate,
        }
        return self.save_config()
