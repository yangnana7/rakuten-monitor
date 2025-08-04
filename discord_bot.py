"""楽天監視システム Discord Bot"""

import os
import sys
import logging
import asyncio
import math
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands

try:
    from .status_report import StatusReporter, get_status_summary, get_items, get_items_count, get_in_stock_items
    from .config_loader import ConfigLoader
    from .exceptions import ConfigurationError
except ImportError:
    from status_report import StatusReporter, get_status_summary, get_items, get_items_count, get_in_stock_items
    from config_loader import ConfigLoader
    from exceptions import ConfigurationError

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot設定
intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


class RakutenMonitorBot:
    """楽天監視システム Discord Bot"""
    
    def __init__(self):
        self.status_reporter = StatusReporter()
        self.bot_start_time = datetime.now()
    
    async def create_status_embed(self, detailed: bool = True) -> discord.Embed:
        """ステータス情報のEmbedを作成"""
        try:
            status = self.status_reporter.get_system_status()
            
            # Embedカラー設定
            if status['system_health'] == 'healthy':
                color = discord.Color.green()
                status_emoji = "✅"
            elif status['system_health'] == 'degraded':
                color = discord.Color.yellow()
                status_emoji = "⚠️"
            else:
                color = discord.Color.red()
                status_emoji = "❌"
            
            embed = discord.Embed(
                title=f"{status_emoji} 楽天監視システム ステータス",
                description=f"システム状態: **{status['system_health'].upper()}**",
                color=color,
                timestamp=datetime.fromisoformat(status['timestamp'])
            )
            
            # 監視状況
            monitoring = status['monitoring']
            monitoring_status = "🟢 アクティブ" if monitoring['monitoring_active'] else "🔴 停止中"
            embed.add_field(
                name="📊 監視状況",
                value=f"状態: {monitoring_status}\n"
                      f"監視URL数: **{monitoring['urls_count']}**\n"
                      f"最近のエラー: **{monitoring['error_count']}件**",
                inline=True
            )
            
            # データベース状況
            database = status['database']
            db_status = "🟢 接続中" if database['connected'] else "🔴 接続エラー"
            db_info = f"状態: {db_status}\n"
            
            if database['connected']:
                db_info += f"登録商品数: **{database.get('total_items', 'N/A')}**\n"
                db_info += f"24h変更: **{database.get('recent_changes_24h', 'N/A')}件**"
            else:
                db_info += f"エラー: {database.get('error', 'Unknown')[:50]}..."
            
            embed.add_field(
                name="🗄️ データベース",
                value=db_info,
                inline=True
            )
            
            # Prometheus状況
            prometheus = status['prometheus']
            if prometheus['enabled']:
                prom_status = "🟢 接続中" if prometheus['reachable'] else "🔴 接続エラー"
                prom_info = f"状態: {prom_status}\n"
                
                if prometheus['reachable'] and 'metrics' in prometheus:
                    metrics = prometheus['metrics']
                    prom_info += f"処理済み: **{metrics.get('items_processed', 0)}**\n"
                    prom_info += f"変更検出: **{metrics.get('changes_found', 0)}**"
                else:
                    prom_info += f"エラー: {prometheus.get('error', 'Unknown')[:30]}..."
            else:
                prom_status = "⚪ 無効"
                prom_info = f"状態: {prom_status}\n理由: {prometheus.get('reason', 'Not configured')}"
            
            embed.add_field(
                name="📈 Prometheus",
                value=prom_info,
                inline=True
            )
            
            # 実行情報
            last_exec = status['last_execution']
            exec_info = f"最終実行: **{last_exec.get('last_run', 'Unknown')}**\n"
            exec_info += f"ステータス: **{last_exec.get('status', 'Unknown')}**"
            
            if 'duration' in last_exec:
                exec_info += f"\n実行時間: **{last_exec['duration']:.1f}秒**"
            
            embed.add_field(
                name="⏱️ 実行状況",
                value=exec_info,
                inline=False
            )
            
            # 詳細情報（エラーメトリクス）
            if detailed and prometheus['reachable'] and 'metrics' in prometheus:
                metrics = prometheus['metrics']
                error_info = []
                
                for key, value in metrics.items():
                    if key.startswith('fail_') and value > 0:
                        error_type = key.replace('fail_', '')
                        error_info.append(f"{error_type}: {value}")
                
                if error_info:
                    embed.add_field(
                        name="🚨 エラー詳細",
                        value="\n".join(error_info),
                        inline=True
                    )
            
            # フッター
            bot_uptime = datetime.now() - self.bot_start_time
            hours, remainder = divmod(int(bot_uptime.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            
            embed.set_footer(
                text=f"Bot稼働時間: {hours}時間{minutes}分 | 更新間隔: 5分"
            )
            
            return embed
            
        except Exception as e:
            logger.error(f"Failed to create status embed: {e}")
            
            # エラー時のフォールバック Embed
            embed = discord.Embed(
                title="❌ ステータス取得エラー",
                description=f"システム情報の取得に失敗しました。\n\nエラー: `{str(e)[:100]}...`",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            return embed
    
    async def create_inventory_embed(self, page: int = 1, filter_type: str = "all") -> discord.Embed:
        """在庫一覧のEmbedを作成"""
        try:
            items_data = get_in_stock_items(page=page, per_page=10, filter_type=filter_type)
            
            # タイトルとカラー設定
            filter_titles = {
                "all": "📦 在庫一覧",
                "new": "🆕 新商品一覧", 
                "restock": "🔄 再販一覧"
            }
            title = filter_titles.get(filter_type, "📦 在庫一覧")
            
            # エラーハンドリング
            if 'error' in items_data:
                embed = discord.Embed(
                    title="❌ 在庫一覧取得エラー",
                    description=f"在庫情報の取得に失敗しました。\n\nエラー: `{items_data['error'][:100]}...`",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                return embed
            
            # ページネーション情報
            pagination = items_data['pagination']
            items = items_data['items']
            
            # Embed作成
            embed = discord.Embed(
                title=f"{title} (ページ {pagination['current_page']}/{pagination['total_pages']})",
                description=f"在庫あり商品: **{pagination['total_items']}件**",
                color=discord.Color.blue(),
                timestamp=datetime.fromisoformat(items_data['timestamp'])
            )
            
            # アイテムが無い場合
            if not items:
                embed.add_field(
                    name="📭 商品なし",
                    value="現在、条件に合う在庫商品はありません。",
                    inline=False
                )
            else:
                # アイテム一覧を表示（短縮版・複数フィールドに分割）
                items_per_field = 3  # フィールドあたり3商品
                field_count = 1
                current_field_text = ""
                
                for i, item in enumerate(items, 1):
                    price_text = f"¥{item['price']:,}" if item['price'] > 0 else "価格不明"
                    
                    # 短縮版表示（商品名は30文字、URLは短縮表示）
                    short_name = item['name'][:30] + ("..." if len(item['name']) > 30 else "")
                    item_text = f"{item['status_emoji']} **{short_name}**\n"
                    item_text += f"💰 {price_text} | 🕐 {item['last_seen']}\n"
                    item_text += f"[商品リンク]({item['url']})\n\n"
                    
                    # フィールドの文字数制限チェック（900文字で余裕を持つ）
                    if len(current_field_text + item_text) > 900 or i % items_per_field == 0:
                        if current_field_text:
                            embed.add_field(
                                name=f"📋 在庫商品 ({field_count})",
                                value=current_field_text.strip(),
                                inline=False
                            )
                            field_count += 1
                            current_field_text = ""
                    
                    current_field_text += item_text
                
                # 残りのアイテムを追加
                if current_field_text:
                    embed.add_field(
                        name=f"📋 在庫商品 ({field_count})",
                        value=current_field_text.strip(),
                        inline=False
                    )
            
            # ページネーション情報
            nav_text = ""
            if pagination['has_prev']:
                nav_text += f"⬅️ `!status -ls --page {pagination['current_page'] - 1}` | "
            if pagination['has_next']:
                nav_text += f"`!status -ls --page {pagination['current_page'] + 1}` ➡️"
            
            if nav_text:
                embed.add_field(
                    name="🔄 ページ移動", 
                    value=nav_text.strip(" | "),
                    inline=False
                )
            
            # フッター
            embed.set_footer(
                text=f"フィルター: {filter_type.upper()} | 🆕NEW 🔄RESTOCK 📦STOCK | 価格順(高→低)"
            )
            
            return embed
            
        except Exception as e:
            logger.error(f"Failed to create inventory embed: {e}")
            
            # エラー時のフォールバック Embed
            embed = discord.Embed(
                title="❌ 在庫一覧取得エラー",
                description=f"在庫情報の作成に失敗しました。\n\nエラー: `{str(e)[:100]}...`",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            return embed
    
    async def create_help_embed(self) -> discord.Embed:
        """ヘルプ情報のEmbedを作成"""
        embed = discord.Embed(
            title="🤖 楽天監視Bot ヘルプ",
            description="楽天商品監視システムの状況を確認できます。",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📋 利用可能なコマンド",
            value="• `!status` - システムの現在状況を表示\n"
                  "• `!status -help` - このヘルプを表示\n"
                  "• `!status -ls [--page N] [--new] [--restock]` - 在庫アイテム一覧を表示\n"
                  "• `!ping` - Bot接続テスト",
            inline=False
        )
        
        embed.add_field(
            name="📦 アイテム一覧コマンド",
            value="• `!status -ls` - 全アイテムの1ページ目\n"
                  "• `!status -ls --page 2` - 2ページ目\n"
                  "• `!status -ls --new` - 新商品のみ\n"
                  "• `!status -ls --restock` - 再販のみ\n"
                  "• 1ページ10件、🆕NEW 🔄RESTOCK 📦STOCK",
            inline=False
        )
        
        embed.add_field(
            name="📊 ステータス情報",
            value="• 監視対象URL数と監視状態\n"
                  "• データベース接続状況\n"
                  "• Prometheus メトリクス\n"
                  "• 最終実行時刻と結果\n"
                  "• エラー統計",
            inline=False
        )
        
        embed.add_field(
            name="🔄 更新頻度",
            value="監視システムは5分間隔で実行されます。\n"
                  "ステータスは実行時にリアルタイムで取得されます。",
            inline=False
        )
        
        embed.add_field(
            name="🏥 ヘルスチェック",
            value="• 🟢 **Healthy**: 正常動作中\n"
                  "• 🟡 **Degraded**: 一部機能に問題\n"
                  "• 🔴 **Critical**: 重大な問題",
            inline=False
        )
        
        embed.set_footer(text="楽天監視システム v1.0 | Step 6 Discord Bot")
        
        return embed


# Bot インスタンス
monitor_bot = RakutenMonitorBot()


@bot.event
async def on_ready():
    """Bot起動時のイベント"""
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Bot のアクティビティを設定
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="楽天商品監視 | !status"
    )
    await bot.change_presence(activity=activity)


@bot.event
async def on_command_error(ctx, error):
    """コマンドエラーハンドリング"""
    if isinstance(error, commands.CommandNotFound):
        # 存在しないコマンドは無視
        return
    
    logger.error(f"Command error in {ctx.command}: {error}")
    
    embed = discord.Embed(
        title="❌ コマンドエラー",
        description=f"コマンドの実行中にエラーが発生しました。\n\n`{str(error)[:100]}...`",
        color=discord.Color.red()
    )
    
    try:
        await ctx.send(embed=embed)
    except:
        pass


@bot.command(name='status')
async def status_command(ctx, *args):
    """システムステータス表示コマンド"""
    logger.info(f"Status command invoked by {ctx.author} in {ctx.guild}")
    
    # 引数解析
    args_list = list(args)
    
    # ヘルプ表示
    if '-help' in args_list or '--help' in args_list or 'help' in args_list:
        embed = await monitor_bot.create_help_embed()
        await ctx.send(embed=embed)
        return
    
    # 在庫一覧表示 (-ls オプション)
    if '-ls' in args_list:
        try:
            # 処理中メッセージ
            processing_msg = await ctx.send("📦 在庫情報を取得中...")
            
            # オプション解析
            page = 1
            filter_type = "all"
            
            # ページ番号取得
            if '--page' in args_list:
                page_idx = args_list.index('--page')
                if page_idx + 1 < len(args_list):
                    try:
                        page = int(args_list[page_idx + 1])
                        page = max(1, page)  # 最小値1
                    except ValueError:
                        page = 1
            
            # フィルタータイプ取得
            if '--new' in args_list:
                filter_type = "new"
            elif '--restock' in args_list:
                filter_type = "restock"
            
            # 在庫一覧Embed作成
            embed = await monitor_bot.create_inventory_embed(page=page, filter_type=filter_type)
            
            # メッセージ更新
            await processing_msg.edit(content=None, embed=embed)
            return
            
        except Exception as e:
            logger.error(f"Failed to execute inventory command: {e}")
            
            error_embed = discord.Embed(
                title="❌ 在庫一覧取得失敗",
                description=f"在庫情報の取得に失敗しました。\n\nエラー: `{str(e)[:100]}...`",
                color=discord.Color.red()
            )
            
            try:
                await processing_msg.edit(content=None, embed=error_embed)
            except:
                await ctx.send(embed=error_embed)
            return
    
    # ステータス表示（デフォルト）
    try:
        # 処理中メッセージ
        processing_msg = await ctx.send("📊 システム状況を確認中...")
        
        # ステータス情報取得
        embed = await monitor_bot.create_status_embed(detailed=True)
        
        # メッセージ更新
        await processing_msg.edit(content=None, embed=embed)
        
    except Exception as e:
        logger.error(f"Failed to execute status command: {e}")
        
        error_embed = discord.Embed(
            title="❌ ステータス取得失敗",
            description=f"システム情報の取得に失敗しました。\n\nエラー: `{str(e)[:100]}...`",
            color=discord.Color.red()
        )
        
        try:
            await ctx.send(embed=error_embed)
        except:
            await ctx.send("ステータス情報の取得に失敗しました。")


@bot.command(name='ping')
async def ping_command(ctx):
    """Bot接続テストコマンド"""
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot レイテンシ: **{latency}ms**",
        color=discord.Color.green()
    )
    
    await ctx.send(embed=embed)


@bot.command(name='status_ls', aliases=['status-ls', 'ls'])
async def status_ls_command(ctx, *args):
    """在庫アイテム一覧表示コマンド"""
    logger.info(f"Status ls command invoked by {ctx.author} in {ctx.guild}")
    
    # デフォルト値
    page = 1
    per_page = 10
    filters = {}
    
    # 引数解析
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == '--page' and i + 1 < len(args):
            try:
                page = max(1, int(args[i + 1]))
                i += 2
            except ValueError:
                await ctx.send("❌ --page オプションには数値を指定してください")
                return
        elif arg == '--new':
            filters['status'] = filters.get('status', []) + ['NEW']
            i += 1
        elif arg == '--restock':
            filters['status'] = filters.get('status', []) + ['RESTOCK']
            i += 1
        else:
            i += 1
    
    try:
        # 処理中メッセージ
        processing_msg = await ctx.send("📦 アイテム一覧を取得中...")
        
        # アイテム取得
        items = get_items(page=page, per_page=per_page, filters=filters)
        total_items = get_items_count(filters=filters)
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
        
        # ページ数調整
        if page > total_pages:
            page = total_pages
            items = get_items(page=page, per_page=per_page, filters=filters)
        
        # Embed作成
        if not items:
            embed = discord.Embed(
                title="📦 Item List",
                description="条件に一致するアイテムがありません",
                color=discord.Color.orange()
            )
        else:
            # フィルタ情報
            filter_text = "All"
            if filters.get('status'):
                filter_text = " / ".join(filters['status'])
            
            embed = discord.Embed(
                title=f"📦 Item List — {filter_text}",
                color=discord.Color.blue()
            )
            
            # アイテム一覧
            items_text = ""
            for item in items:
                status = item['status']
                
                # ステータス別の色付け（テキストでは絵文字で表現）
                if status == 'NEW':
                    status_emoji = "🆕"
                elif status == 'RESTOCK':
                    status_emoji = "🔄"
                elif status == 'STOCK':
                    status_emoji = "📦"
                else:
                    status_emoji = "❓"
                
                # 価格のフォーマット
                price_text = f"¥{item['price']:,}" if item['price'] else "価格不明"
                
                # タイトルを短縮（長すぎる場合）
                title = item['title']
                if len(title) > 60:
                    title = title[:57] + "..."
                
                items_text += f"{status_emoji} [{title}]({item['url']}) — {price_text} — {status}\n"
            
            embed.description = items_text
            
            # フッター
            embed.set_footer(text=f"Page {page} / {total_pages} · Showing {len(items)} of {total_items} items")
        
        # メッセージ更新
        await processing_msg.edit(content=None, embed=embed)
        
    except Exception as e:
        logger.error(f"Failed to execute status ls command: {e}")
        
        error_embed = discord.Embed(
            title="❌ アイテム一覧取得失敗",
            description=f"アイテム情報の取得に失敗しました。\n\nエラー: `{str(e)[:100]}...`",
            color=discord.Color.red()
        )
        
        try:
            await ctx.send(embed=error_embed)
        except:
            await ctx.send("アイテム一覧の取得に失敗しました。")


def main():
    """Bot のメイン関数"""
    # 環境変数チェック
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not bot_token:
        logger.error("DISCORD_BOT_TOKEN environment variable is not set")
        logger.error("Please set your Discord bot token in the environment file")
        sys.exit(1)
    
    # CI環境でのWebSocket接続スキップ
    if os.getenv('CI'):
        logger.info("CI environment detected, skipping WebSocket connection")
        sys.exit(0)
    
    # 設定ファイル確認
    try:
        config = ConfigLoader()
        config.load_config()
        logger.info("Configuration loaded successfully")
    except ConfigurationError as e:
        logger.warning(f"Configuration issue: {e}")
        logger.warning("Bot will start but some features may be limited")
    
    # Bot起動
    try:
        logger.info("Starting Rakuten Monitor Discord Bot...")
        bot.run(bot_token, log_level=logging.INFO)
    except discord.LoginFailure:
        logger.error("Invalid Discord bot token")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()