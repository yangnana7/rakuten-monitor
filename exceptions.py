"""楽天商品監視ツール用カスタム例外"""


class RakutenMonitorError(Exception):
    """楽天監視ツールの基底例外クラス"""
    pass


class LayoutChangeError(RakutenMonitorError):
    """ページのHTML構造が変更された際に発生する例外"""
    pass


class DatabaseConnectionError(RakutenMonitorError):
    """データベース接続エラー"""
    pass


class ConfigurationError(RakutenMonitorError):
    """設定ファイルの読み込みエラー"""
    pass


class DiscordNotificationError(RakutenMonitorError):
    """Discord通知送信エラー"""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
    
    def __str__(self):
        base_msg = super().__str__()
        if self.status_code:
            return f"{base_msg} (HTTP {self.status_code})"
        return base_msg


class PrometheusError(RakutenMonitorError):
    """Prometheus メトリクス送信エラー"""
    
    def __init__(self, message: str, metric_name: str = None):
        super().__init__(message)
        self.metric_name = metric_name


class NetworkError(RakutenMonitorError):
    """ネットワーク接続エラー"""
    
    def __init__(self, message: str, url: str = None, timeout: bool = False):
        super().__init__(message)
        self.url = url
        self.timeout = timeout