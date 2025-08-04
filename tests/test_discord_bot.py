"""Discord Bot機能のテスト"""

import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

# テスト実行時のモジュールパス設定
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands

# CI環境でのWebSocket接続をスキップ
os.environ['CI'] = '1'

from discord_bot import RakutenMonitorBot, bot
from status_report import StatusReporter


class TestRakutenMonitorBot:
    """RakutenMonitorBot クラスのテスト"""
    
    @pytest.fixture
    def monitor_bot(self):
        """テスト用のRakutenMonitorBotインスタンス"""
        return RakutenMonitorBot()
    
    @pytest.fixture
    def mock_status_data(self):
        """モックステータスデータ"""
        return {
            'timestamp': '2025-08-04T12:00:00',
            'system_health': 'healthy',
            'monitoring': {
                'urls_count': 5,
                'monitoring_active': True,
                'error_count': 0,
                'config_valid': True
            },
            'database': {
                'connected': True,
                'total_items': 150,
                'recent_changes_24h': 3,
                'last_check': '2025-08-04T12:00:00'
            },
            'prometheus': {
                'enabled': True,
                'reachable': True,
                'url': 'http://localhost:9091',
                'metrics': {
                    'items_processed': 45,
                    'changes_found': 2,
                    'fail_network': 1,
                    'fail_layout': 0
                },
                'last_check': '2025-08-04T12:00:00'
            },
            'last_execution': {
                'last_run': '2025-08-04 11:55:00',
                'status': 'completed',
                'duration': 12.5,
                'source': 'systemd_log'
            }
        }
    
    @pytest.mark.asyncio
    async def test_create_status_embed_healthy(self, monitor_bot, mock_status_data):
        """正常なシステム状態でのEmbed作成テスト"""
        with patch.object(monitor_bot.status_reporter, 'get_system_status', return_value=mock_status_data):
            embed = await monitor_bot.create_status_embed(detailed=True)
            
            # 基本情報の確認
            assert "楽天監視システム ステータス" in embed.title
            assert "✅" in embed.title
            assert "HEALTHY" in embed.description
            assert embed.color == discord.Color.green()
            
            # フィールド数の確認（監視、DB、Prometheus、実行状況、エラー詳細）
            assert len(embed.fields) >= 4
            
            # 各フィールドの内容確認
            field_names = [field.name for field in embed.fields]
            assert "📊 監視状況" in field_names
            assert "🗄️ データベース" in field_names
            assert "📈 Prometheus" in field_names
            assert "⏱️ 実行状況" in field_names
    
    @pytest.mark.asyncio
    async def test_create_status_embed_degraded(self, monitor_bot, mock_status_data):
        """劣化したシステム状態でのEmbed作成テスト"""
        # システム状態を劣化に変更
        mock_status_data['system_health'] = 'degraded'
        mock_status_data['database']['connected'] = False
        mock_status_data['database']['error'] = 'Connection timeout'
        
        with patch.object(monitor_bot.status_reporter, 'get_system_status', return_value=mock_status_data):
            embed = await monitor_bot.create_status_embed(detailed=True)
            
            # 劣化状態の確認
            assert "⚠️" in embed.title
            assert "DEGRADED" in embed.description
            assert embed.color == discord.Color.yellow()
            
            # データベースエラー情報の確認
            db_field = next((field for field in embed.fields if "データベース" in field.name), None)
            assert db_field is not None
            assert "🔴 接続エラー" in db_field.value
            assert "Connection timeout" in db_field.value
    
    @pytest.mark.asyncio
    async def test_create_status_embed_critical(self, monitor_bot, mock_status_data):
        """重大なシステム状態でのEmbed作成テスト"""
        # システム状態を重大に変更
        mock_status_data['system_health'] = 'critical'
        mock_status_data['monitoring']['monitoring_active'] = False
        mock_status_data['monitoring']['error_count'] = 10
        
        with patch.object(monitor_bot.status_reporter, 'get_system_status', return_value=mock_status_data):
            embed = await monitor_bot.create_status_embed(detailed=True)
            
            # 重大状態の確認
            assert "❌" in embed.title
            assert "CRITICAL" in embed.description
            assert embed.color == discord.Color.red()
            
            # 監視停止状態の確認
            monitoring_field = next((field for field in embed.fields if "監視状況" in field.name), None)
            assert monitoring_field is not None
            assert "🔴 停止中" in monitoring_field.value
            assert "10件" in monitoring_field.value
    
    @pytest.mark.asyncio
    async def test_create_help_embed(self, monitor_bot):
        """ヘルプEmbed作成テスト"""
        embed = await monitor_bot.create_help_embed()
        
        # ヘルプ情報の確認
        assert "楽天監視Bot ヘルプ" in embed.title
        assert "🤖" in embed.title
        assert embed.color == discord.Color.blue()
        
        # フィールド内容の確認
        field_names = [field.name for field in embed.fields]
        assert "📋 利用可能なコマンド" in field_names
        assert "📊 ステータス情報" in field_names
        assert "🔄 更新頻度" in field_names
        assert "🏥 ヘルスチェック" in field_names
        
        # コマンド情報の確認
        commands_field = next((field for field in embed.fields if "利用可能なコマンド" in field.name), None)
        assert "!status" in commands_field.value
        assert "!status -help" in commands_field.value
    
    @pytest.mark.asyncio
    async def test_create_status_embed_error_handling(self, monitor_bot):
        """ステータス取得エラー時のEmbed作成テスト"""
        with patch.object(monitor_bot.status_reporter, 'get_system_status', side_effect=Exception("Test error")):
            embed = await monitor_bot.create_status_embed(detailed=True)
            
            # エラー時のフォールバック確認
            assert "❌ ステータス取得エラー" in embed.title
            assert embed.color == discord.Color.red()
            assert "Test error" in embed.description


class TestDiscordBotCommands:
    """Discord Bot コマンドのテスト"""
    
    @pytest.fixture
    def mock_ctx(self):
        """モックコンテキスト"""
        ctx = AsyncMock()
        ctx.author = Mock()
        ctx.author.name = "test_user"
        ctx.guild = Mock()
        ctx.guild.name = "test_guild"
        ctx.send = AsyncMock()
        return ctx
    
    @pytest.fixture
    def mock_message(self):
        """モック処理中メッセージ"""
        msg = AsyncMock()
        msg.edit = AsyncMock()
        return msg
    
    @pytest.mark.asyncio
    async def test_status_command_success(self, mock_ctx, mock_message):
        """!statusコマンド成功テスト"""
        # モック設定
        mock_ctx.send.return_value = mock_message
        
        with patch('discord_bot.monitor_bot') as mock_monitor_bot:
            mock_embed = Mock()
            mock_monitor_bot.create_status_embed = AsyncMock(return_value=mock_embed)
            
            # コマンド実行
            from discord_bot import status_command
            await status_command(mock_ctx)
            
            # 呼び出し確認
            mock_ctx.send.assert_called_once_with("📊 システム状況を確認中...")
            mock_message.edit.assert_called_once_with(content=None, embed=mock_embed)
            mock_monitor_bot.create_status_embed.assert_called_once_with(detailed=True)
    
    @pytest.mark.asyncio
    async def test_status_command_help(self, mock_ctx):
        """!status -helpコマンドテスト"""
        with patch('discord_bot.monitor_bot') as mock_monitor_bot:
            mock_embed = Mock()
            mock_monitor_bot.create_help_embed = AsyncMock(return_value=mock_embed)
            
            # ヘルプコマンド実行
            from discord_bot import status_command
            await status_command(mock_ctx, '-help')
            
            # 呼び出し確認
            mock_ctx.send.assert_called_once_with(embed=mock_embed)
            mock_monitor_bot.create_help_embed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_status_command_error(self, mock_ctx, mock_message):
        """!statusコマンドエラーテスト"""
        # モック設定
        mock_ctx.send.return_value = mock_message
        
        with patch('discord_bot.monitor_bot') as mock_monitor_bot:
            mock_monitor_bot.create_status_embed = AsyncMock(side_effect=Exception("Test error"))
            
            # コマンド実行
            from discord_bot import status_command
            await status_command(mock_ctx)
            
            # エラー処理の確認
            mock_ctx.send.assert_called()
            call_args = mock_ctx.send.call_args_list[-1]
            
            # エラーメッセージ確認
            if 'embed' in call_args[1]:
                error_embed = call_args[1]['embed']
                assert "ステータス取得失敗" in str(error_embed.title) or "システム情報の取得に失敗" in str(error_embed.description)
    
    @pytest.mark.asyncio
    async def test_ping_command(self, mock_ctx):
        """!pingコマンドテスト"""
        with patch('discord_bot.bot') as mock_bot:
            mock_bot.latency = 0.05  # 50ms
            
            from discord_bot import ping_command
            await ping_command(mock_ctx)
            
            # 呼び出し確認
            mock_ctx.send.assert_called_once()
            call_args = mock_ctx.send.call_args[1]
            embed = call_args['embed']
            
            assert "🏓 Pong!" in embed.title
            assert "50ms" in embed.description


class TestStatusReporter:
    """StatusReporter クラスのテスト"""
    
    @pytest.fixture
    def status_reporter(self):
        """テスト用のStatusReporterインスタンス"""
        return StatusReporter()
    
    def test_status_reporter_init(self, status_reporter):
        """StatusReporter初期化テスト"""
        assert status_reporter.config_path == "config.json"
    
    @patch('status_report.ConfigLoader')
    def test_get_monitoring_status_success(self, mock_config_loader, status_reporter):
        """監視ステータス取得成功テスト"""
        # モック設定
        mock_config_instance = Mock()
        mock_config_instance.load_config.return_value = {
            'urls': ['http://test1.com', 'http://test2.com']
        }
        mock_config_loader.return_value = mock_config_instance
        
        with patch.object(status_reporter, '_is_monitoring_active', return_value=True), \
             patch.object(status_reporter, '_get_recent_error_count', return_value=2):
            
            result = status_reporter._get_monitoring_status()
            
            assert result['urls_count'] == 2
            assert result['monitoring_active'] == True
            assert result['error_count'] == 2
            assert result['config_valid'] == True
    
    @patch('status_report.ItemDB')
    def test_get_database_status_success(self, mock_itemdb, status_reporter):
        """データベースステータス取得成功テスト"""
        # モック設定
        mock_db_instance = Mock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            (1,),  # SELECT 1 のレスポンス
            (100,),  # アイテム数
            (5,)   # 最近の変更数
        ]
        # コンテキストマネージャーを正しく設定
        mock_cursor_context = MagicMock()
        mock_cursor_context.__enter__.return_value = mock_cursor
        mock_cursor_context.__exit__.return_value = None
        mock_db_instance.connection.cursor.return_value = mock_cursor_context
        mock_itemdb.return_value.__enter__.return_value = mock_db_instance
        
        result = status_reporter._get_database_status()
        
        assert result['connected'] == True
        assert result['total_items'] == 100
        assert result['recent_changes_24h'] == 5
        assert 'last_check' in result
    
    @patch('status_report.requests.get')
    def test_get_prometheus_status_success(self, mock_get, status_reporter):
        """Prometheusステータス取得成功テスト"""
        # モック設定
        os.environ['PROM_PUSHGATEWAY_URL'] = 'http://localhost:9091'
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
monitor_fail_total{type="network",instance="localhost"} 2
monitor_fail_total{type="db",instance="localhost"} 0
monitor_items_processed_total{instance="localhost"} 50
monitor_changes_found_total{instance="localhost"} 3
'''
        mock_get.return_value = mock_response
        
        result = status_reporter._get_prometheus_status()
        
        assert result['enabled'] == True
        assert result['reachable'] == True
        assert result['url'] == 'http://localhost:9091'
        assert result['metrics']['fail_network'] == 2
        assert result['metrics']['fail_db'] == 0
        assert result['metrics']['items_processed'] == 50
        assert result['metrics']['changes_found'] == 3
        
        # クリーンアップ
        del os.environ['PROM_PUSHGATEWAY_URL']
    
    def test_get_prometheus_status_disabled(self, status_reporter):
        """Prometheus無効時のステータステスト"""
        # PROM_PUSHGATEWAY_URLが未設定の場合
        if 'PROM_PUSHGATEWAY_URL' in os.environ:
            del os.environ['PROM_PUSHGATEWAY_URL']
        
        result = status_reporter._get_prometheus_status()
        
        assert result['enabled'] == False
        assert result['reachable'] == False
        assert 'not configured' in result['reason']


@pytest.mark.skipif(os.getenv('CI'), reason="CI環境ではWebSocket接続をスキップ")
class TestBotIntegration:
    """Bot統合テスト（CI環境以外）"""
    
    def test_bot_configuration(self):
        """Bot設定テスト"""
        assert bot.command_prefix == '!'
        assert bot.intents.message_content == True
    
    def test_bot_commands_registered(self):
        """Botコマンド登録テスト"""
        command_names = [cmd.name for cmd in bot.commands]
        assert 'status' in command_names
        assert 'ping' in command_names


if __name__ == "__main__":
    # テスト実行
    pytest.main([__file__, '-v'])