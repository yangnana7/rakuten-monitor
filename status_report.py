"""監視システムの稼働状況を収集するユーティリティ"""

import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import requests
from pathlib import Path

try:
    from .config_loader import ConfigLoader
    from .item_db import ItemDB
    from .exceptions import DatabaseConnectionError, PrometheusError
except ImportError:
    from config_loader import ConfigLoader
    from item_db import ItemDB
    from exceptions import DatabaseConnectionError, PrometheusError

logger = logging.getLogger(__name__)


class StatusReporter:
    """監視システムのステータス情報を収集・報告"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        
    def get_system_status(self) -> Dict[str, Any]:
        """システム全体のステータスを取得"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'monitoring': self._get_monitoring_status(),
            'database': self._get_database_status(),
            'prometheus': self._get_prometheus_status(),
            'last_execution': self._get_last_execution_info(),
            'system_health': 'healthy'
        }
        
        # 全体的な健全性判定
        if not status['database']['connected'] or status['monitoring']['error_count'] > 5:
            status['system_health'] = 'degraded'
        
        return status
    
    def _get_monitoring_status(self) -> Dict[str, Any]:
        """監視の状況を取得"""
        try:
            config = ConfigLoader(self.config_path)
            config_data = config.load_config()
            
            return {
                'urls_count': len(config_data.get('urls', [])),
                'monitoring_active': self._is_monitoring_active(),
                'error_count': self._get_recent_error_count(),
                'config_valid': True
            }
        except Exception as e:
            logger.error(f"Failed to get monitoring status: {e}")
            return {
                'urls_count': 0,
                'monitoring_active': False,
                'error_count': 0,
                'config_valid': False,
                'error': str(e)
            }
    
    def _get_database_status(self) -> Dict[str, Any]:
        """データベースの状況を取得"""
        try:
            with ItemDB() as db:
                with db.connection.cursor() as cursor:
                    # 基本接続テスト
                    cursor.execute("SELECT 1;")
                    cursor.fetchone()
                    
                    # アイテム数取得
                    cursor.execute("SELECT COUNT(*) FROM items;")
                    item_count = cursor.fetchone()[0]
                    
                    # 最近の変更数
                    cursor.execute("""
                        SELECT COUNT(*) FROM items 
                        WHERE updated_at > NOW() - INTERVAL '24 hours';
                    """)
                    recent_changes = cursor.fetchone()[0]
                    
                return {
                    'connected': True,
                    'total_items': item_count,
                    'recent_changes_24h': recent_changes,
                    'last_check': datetime.now().isoformat()
                }
        except DatabaseConnectionError as e:
            return {
                'connected': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': f"Unexpected database error: {e}",
                'last_check': datetime.now().isoformat()
            }
    
    def _get_prometheus_status(self) -> Dict[str, Any]:
        """Prometheusの状況を取得"""
        pushgateway_url = os.getenv('PROM_PUSHGATEWAY_URL')
        
        if not pushgateway_url:
            return {
                'enabled': False,
                'reachable': False,
                'reason': 'PROM_PUSHGATEWAY_URL not configured'
            }
        
        try:
            # Pushgatewayへの疎通確認
            response = requests.get(f"{pushgateway_url}/metrics", timeout=5)
            
            if response.status_code == 200:
                # メトリクス解析
                metrics = self._parse_prometheus_metrics(response.text)
                return {
                    'enabled': True,
                    'reachable': True,
                    'url': pushgateway_url,
                    'metrics': metrics,
                    'last_check': datetime.now().isoformat()
                }
            else:
                return {
                    'enabled': True,
                    'reachable': False,
                    'error': f"HTTP {response.status_code}",
                    'last_check': datetime.now().isoformat()
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'enabled': True,
                'reachable': False,
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
    
    def _parse_prometheus_metrics(self, metrics_text: str) -> Dict[str, int]:
        """Prometheusメトリクスをパース"""
        metrics = {}
        
        for line in metrics_text.split('\n'):
            if line.startswith('monitor_fail_total'):
                # monitor_fail_total{type="db",instance="localhost"} 1
                if '{' in line and '}' in line:
                    labels_part = line[line.find('{')+1:line.find('}')]
                    value_part = line.split()[-1]
                    
                    try:
                        # type="db" などからtypeを抽出
                        for label in labels_part.split(','):
                            if label.strip().startswith('type='):
                                error_type = label.split('=')[1].strip('"')
                                metrics[f'fail_{error_type}'] = int(value_part)
                                break
                    except (IndexError, ValueError):
                        continue
            
            elif line.startswith('monitor_items_processed_total'):
                try:
                    metrics['items_processed'] = int(line.split()[-1])
                except (IndexError, ValueError):
                    continue
            
            elif line.startswith('monitor_changes_found_total'):
                try:
                    metrics['changes_found'] = int(line.split()[-1])
                except (IndexError, ValueError):
                    continue
        
        return metrics
    
    def _get_last_execution_info(self) -> Dict[str, Any]:
        """最後の実行情報を取得"""
        try:
            # systemdログから最後の実行を確認
            result = subprocess.run([
                'journalctl', '-u', 'rakuten-monitor', '-n', '10', '--no-pager', '--quiet'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in reversed(lines):
                    if 'monitoring completed' in line.lower() or 'processing url' in line.lower():
                        # ログから時刻を抽出
                        try:
                            # 例: Dec 25 10:30:45
                            log_parts = line.split()[:3]
                            timestamp_str = ' '.join(log_parts)
                            # 簡単な時刻パース（年は現在年を仮定）
                            current_year = datetime.now().year
                            full_timestamp = f"{current_year} {timestamp_str}"
                            
                            return {
                                'last_run': full_timestamp,
                                'source': 'systemd_log',
                                'status': 'completed' if 'completed' in line.lower() else 'running'
                            }
                        except:
                            pass
            
            # systemdログが取得できない場合、ファイルベースの情報を確認
            status_file = Path('/tmp/rakuten_monitor_status.json')
            if status_file.exists():
                try:
                    with open(status_file, 'r') as f:
                        status_data = json.load(f)
                    return {
                        'last_run': status_data.get('last_run', 'unknown'),
                        'source': 'status_file',
                        'duration': status_data.get('duration_seconds', 0),
                        'status': status_data.get('status', 'unknown')
                    }
                except:
                    pass
            
            return {
                'last_run': 'unknown',
                'source': 'none',
                'status': 'unknown'
            }
            
        except Exception as e:
            logger.error(f"Failed to get last execution info: {e}")
            return {
                'last_run': 'error',
                'source': 'error',
                'error': str(e)
            }
    
    def _is_monitoring_active(self) -> bool:
        """監視が現在アクティブかチェック"""
        try:
            # systemdサービスの状態確認
            result = subprocess.run([
                'systemctl', 'is-active', 'rakuten-monitor.timer'
            ], capture_output=True, text=True, timeout=5)
            
            return result.returncode == 0 and result.stdout.strip() == 'active'
            
        except Exception:
            return False
    
    def _get_recent_error_count(self) -> int:
        """最近のエラー回数を取得"""
        try:
            # 過去24時間のエラーログをカウント
            result = subprocess.run([
                'journalctl', '-u', 'rakuten-monitor', '--since', '24 hours ago',
                '--no-pager', '--quiet'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                error_count = result.stdout.count('ERROR') + result.stdout.count('CRITICAL')
                return error_count
            
            return 0
            
        except Exception:
            return 0
    
    def get_status_summary(self) -> str:
        """ステータスの簡潔な要約を取得"""
        status = self.get_system_status()
        
        if status['system_health'] == 'healthy':
            return f"✅ System Healthy - Monitoring {status['monitoring']['urls_count']} URLs"
        elif status['system_health'] == 'degraded':
            return f"⚠️ System Degraded - {status['monitoring']['error_count']} recent errors"
        else:
            return f"❌ System Issues Detected"


def get_quick_status() -> Dict[str, Any]:
    """クイックステータス取得（モジュール関数）"""
    reporter = StatusReporter()
    return reporter.get_system_status()


def get_status_summary() -> str:
    """ステータス要約取得（モジュール関数）"""
    reporter = StatusReporter()
    return reporter.get_status_summary()


def get_items(page: int = 1, per_page: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    ページネーション付きでアイテム一覧を取得
    
    Args:
        page: ページ番号（1から開始）
        per_page: 1ページあたりの件数
        filters: フィルタ条件 {'status': ['NEW', 'RESTOCK']} など
    
    Returns:
        アイテムのリスト。各アイテムは以下の形式:
        {'title': str, 'url': str, 'price': int, 'status': str, 'updated_at': str}
    """
    try:
        try:
            from .item_db import ItemDB
        except ImportError:
            from item_db import ItemDB
        
        with ItemDB() as db:
            with db.connection.cursor() as cursor:
                # WHERE句を構築
                where_conditions = []
                params = []
                
                if filters and 'status' in filters:
                    status_list = filters['status']
                    if status_list:
                        placeholders = ','.join(['%s'] * len(status_list))
                        where_conditions.append(f"status IN ({placeholders})")
                        params.extend(status_list)
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # オフセット計算
                offset = (page - 1) * per_page
                
                # SQLクエリ実行 (URLカラムがない場合に備えて、item_codeをURLとして使用)
                query = f"""
                    SELECT 
                        title,
                        CASE 
                            WHEN item_code LIKE 'http%' THEN item_code
                            ELSE CONCAT('https://item.rakuten.co.jp/shop/item/', item_code)
                        END as url,
                        price,
                        status,
                        updated_at
                    FROM items 
                    {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """
                
                params.extend([per_page, offset])
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                items = []
                
                for row in rows:
                    items.append({
                        'title': row[0] or 'No Title',
                        'url': row[1] or '#',
                        'price': row[2] or 0,
                        'status': row[3] or 'UNKNOWN',
                        'updated_at': row[4].isoformat() if row[4] else datetime.now().isoformat()
                    })
                
                return items
                
    except Exception as e:
        logger.error(f"Failed to get items: {e}")
        return []


def get_items_count(filters: Optional[Dict[str, Any]] = None) -> int:
    """
    フィルタ条件に合致するアイテムの総数を取得
    
    Args:
        filters: フィルタ条件 {'status': ['NEW', 'RESTOCK']} など
    
    Returns:
        総件数
    """
    try:
        try:
            from .item_db import ItemDB
        except ImportError:
            from item_db import ItemDB
        
        with ItemDB() as db:
            with db.connection.cursor() as cursor:
                # WHERE句を構築
                where_conditions = []
                params = []
                
                if filters and 'status' in filters:
                    status_list = filters['status']
                    if status_list:
                        placeholders = ','.join(['%s'] * len(status_list))
                        where_conditions.append(f"status IN ({placeholders})")
                        params.extend(status_list)
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                query = f"SELECT COUNT(*) FROM items {where_clause}"
                cursor.execute(query, params)
                
                return cursor.fetchone()[0]
                
    except Exception as e:
        logger.error(f"Failed to get items count: {e}")
        return 0


if __name__ == "__main__":
    # CLI実行時のテスト
    import pprint
    
    print("=== Rakuten Monitor Status Report ===")
    reporter = StatusReporter()
    status = reporter.get_system_status()
    
    pprint.pprint(status, width=80)
    print(f"\nSummary: {reporter.get_status_summary()}")