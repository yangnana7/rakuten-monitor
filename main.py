"""メイン CLI モジュール - Phase4."""

# 1. ――― もっとも早く SIGINT / SIGTERM を捕捉する -------------------------
import os
import signal
import sys


def _graceful_exit(sig, frame) -> None:
    """どのタイミングでも必ず exit-code 0 で終了させる。"""
    os._exit(0)  # ← sys.exit ではなく os._exit


signal.signal(signal.SIGINT, _graceful_exit)
signal.signal(signal.SIGTERM, _graceful_exit)
# --------------------------------------------------------------------------

# 2. ――― 重い依存は遅延 import --------------------------------------------
import argparse  # noqa: E402
import logging  # noqa: E402
import importlib  # noqa: E402
from typing import List, Optional  # noqa: E402

monitor = importlib.import_module("app.main")
scheduler = importlib.import_module("scheduler")
# --------------------------------------------------------------------------

# ログ設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(args: Optional[List[str]] = None) -> None:
    """
    CLI入口：--once / --daemon / --interval をサポート。

    Args:
        args (List[str], optional): コマンドライン引数。Noneの場合はsys.argvを使用
    """
    try:
        parser = argparse.ArgumentParser(
            description="Rakuten Product Monitor - Phase 4",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  python main.py --once                    # 一回だけ監視実行
  python main.py --daemon                  # デーモンモードで15秒間隔実行
  python main.py --daemon --interval 30   # デーモンモードで30秒間隔実行
            """,
        )

        # Create mutually exclusive group for --once and --daemon
        mode_group = parser.add_mutually_exclusive_group()

        mode_group.add_argument(
            "--once", action="store_true", help="run single check and exit"
        )

        mode_group.add_argument(
            "--daemon", action="store_true", help="デーモンモードで継続実行"
        )

        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="scheduler loop interval in seconds",
        )

        parser.add_argument(
            "--max-runs", type=int, help="maximum number of runs (for non-daemon mode)"
        )

        try:
            parsed_args = parser.parse_args(args)

            if parsed_args.once:
                monitor.run_monitor_once()
                sys.exit(0)
            elif parsed_args.daemon:
                scheduler.start(interval=parsed_args.interval)
            else:
                scheduler.start(
                    interval=parsed_args.interval,
                    max_runs=getattr(parsed_args, "max_runs", None),
                )

        except SystemExit:
            # argparseがエラー時にSystemExitを発生させる
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
