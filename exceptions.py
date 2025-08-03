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
    pass