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
                "global_settings": {"silence_duration": 0.3, "scale_rate": 1.0},
                "speaker_settings": {},
            }
            return default_config

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                info(f"已加载配置文件: {self.config_file}")
                # 确保配置文件有正确的结构
                if "global_settings" not in config:
                    config["global_settings"] = {
                        "silence_duration": 0.3,
                        "scale_rate": 1.0,
                    }
                if "speaker_settings" not in config:
                    config["speaker_settings"] = {}
                return config
        except Exception as e:
            error(f"加载配置文件失败: {str(e)}")
            # 返回默认配置
            return {
                "global_settings": {"silence_duration": 0.3, "scale_rate": 1.0},
                "speaker_settings": {},
            }

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

    def get_audio_settings(self, speaker=None):
        """获取音频设置，如果提供了speaker则获取对应角色的设置，否则返回全局设置"""
        default_settings = {"silence_duration": 0.3, "scale_rate": 1.0}

        if speaker and speaker != "无":
            # 获取指定角色的设置，如果没有则使用全局设置
            speaker_settings = self.config.get("speaker_settings", {}).get(
                speaker, None
            )
            if speaker_settings:
                return speaker_settings
            
        # 返回全局设置
        return self.config.get("global_settings", default_settings)

    def save_audio_settings(self, speaker, silence_duration, scale_rate):
        """保存音频设置，如果提供了speaker则保存为对应角色的设置，否则保存为全局设置"""
        settings = {
            "silence_duration": silence_duration,
            "scale_rate": scale_rate,
        }

        if speaker and speaker != "无":
            # 保存到指定角色的设置
            if "speaker_settings" not in self.config:
                self.config["speaker_settings"] = {}
            self.config["speaker_settings"][speaker] = settings
            info(f"已保存角色 '{speaker}' 的音频设置")
        else:
            # 保存到全局设置
            self.config["global_settings"] = settings
            info("已保存全局音频设置")

        return self.save_config()
