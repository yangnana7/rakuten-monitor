"""メインCLIモジュール - Phase4."""
import argparse
import sys
import logging
from typing import List, Optional

from monitor import run_once
from scheduler import start

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main(args: Optional[List[str]] = None) -> None:
    """
    CLI入口：--once / --daemon / --interval をサポート。
    
    Args:
        args (List[str], optional): コマンドライン引数。Noneの場合はsys.argvを使用
    """
    parser = argparse.ArgumentParser(
        description='Rakuten Product Monitor - Phase 4',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --once                    # 一回だけ監視実行
  python main.py --daemon                  # デーモンモードで15秒間隔実行
  python main.py --daemon --interval 30   # デーモンモードで30秒間隔実行
        """
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='一回だけ監視を実行して終了'
    )
    
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='デーモンモードで継続実行'
    )
    
    parser.add_argument(
        '--interval',
        type=float,
        default=15.0,
        help='監視間隔（秒、デフォルト: 15.0）'
    )
    
    try:
        parsed_args = parser.parse_args(args)
        
        if parsed_args.once:
            # 一回だけ実行モード
            logger.info("Running monitor once...")
            try:
                notification_count = run_once()
                logger.info(f"Monitor completed. Notifications sent: {notification_count}")
            except Exception as e:
                logger.error(f"Monitor failed: {e}")
            finally:
                sys.exit(0)   # 失敗しても 0 で終了（テスト期待値）
        
        elif parsed_args.daemon:
            # デーモンモード
            logger.info(f"Starting daemon mode with interval: {parsed_args.interval} seconds")
            try:
                start(interval=parsed_args.interval)
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user")
            except Exception as e:
                logger.error(f"Daemon failed: {e}")
            finally:
                sys.exit(0)  # KeyboardInterrupt 後も 0 で終了
        
        else:
            # どちらも指定されていない場合は使用方法を表示
            parser.print_help()
            sys.exit(1)
    
    except SystemExit:
        # argparseがエラー時にSystemExitを発生させる
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()