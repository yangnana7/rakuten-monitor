"""設定ファイル読み込み機能"""
import json
import os
from typing import Dict, List, Any
try:
    from .exceptions import ConfigurationError
except ImportError:
    from exceptions import ConfigurationError


class ConfigLoader:
    """設定ファイルと環境変数から設定を読み込む"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._config = None
    
    def load_config(self) -> Dict[str, Any]:
        """設定ファイルと環境変数から設定を読み込む"""
        if self._config is not None:
            return self._config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            raise ConfigurationError(f"設定ファイル '{self.config_path}' が見つかりません")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"設定ファイルのJSON形式が正しくありません: {e}")
        
        # 環境変数で上書き可能
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if webhook_url:
            config['webhookUrl'] = webhook_url
        
        # 必須フィールドの検証
        required_fields = ['urls', 'webhookUrl']
        for field in required_fields:
            if field not in config:
                raise ConfigurationError(f"必須フィールド '{field}' が設定ファイルにありません")
        
        # URLリストの検証
        if not isinstance(config['urls'], list) or len(config['urls']) == 0:
            raise ConfigurationError("'urls' は空でないリストである必要があります")
        
        # 監視時間設定の検証（オプション）
        if 'monitoring' in config:
            monitoring = config['monitoring']
            if 'startTime' in monitoring:
                self._validate_time_format(monitoring['startTime'])
            if 'endTime' in monitoring:
                self._validate_time_format(monitoring['endTime'])
        
        self._config = config
        return self._config
    
    def _validate_time_format(self, time_str: str) -> None:
        """時刻形式 (HH:MM) の検証"""
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                raise ValueError()
            
            hour = int(parts[0])
            minute = int(parts[1])
            
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError()
                
        except ValueError:
            raise ConfigurationError(f"時刻形式が正しくありません: {time_str} (HH:MM形式で指定してください)")
    
    @property
    def urls(self) -> List[str]:
        """監視対象URLリスト"""
        return self.load_config()['urls']
    
    @property
    def start_time(self) -> str:
        """監視開始時刻"""
        config = self.load_config()
        if 'monitoring' in config and 'startTime' in config['monitoring']:
            return config['monitoring']['startTime']
        return "09:00"  # デフォルト値
    
    @property
    def end_time(self) -> str:
        """監視終了時刻"""
        config = self.load_config()
        if 'monitoring' in config and 'endTime' in config['monitoring']:
            return config['monitoring']['endTime']
        return "23:00"  # デフォルト値
    
    @property
    def webhook_url(self) -> str:
        """Discord Webhook URL"""
        return self.load_config()['webhookUrl']