#!/usr/bin/env python3
"""
Redis Watchdog - Redis pub/sub 接続監視・自動復旧機能
"""

import asyncio
import logging
import os
import redis.asyncio as redis
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class RedisWatchdog:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.channels = ["rakuten_monitor", "interval_updates"]
        self.watchdog_interval = 30  # 30秒ごとにチェック
        self.is_running = False

    async def connect(self) -> bool:
        """Redis接続を確立"""
        try:
            self.client = redis.from_url(self.redis_url)

            # 接続テスト
            await self.client.ping()
            logger.info("Redis connection established")

            # pub/sub設定
            self.pubsub = self.client.pubsub()

            # チャンネル購読
            for channel in self.channels:
                await self.pubsub.subscribe(channel)
                logger.info(f"Subscribed to channel: {channel}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False

    async def disconnect(self):
        """Redis接続を切断"""
        try:
            if self.pubsub:
                await self.pubsub.unsubscribe()
                await self.pubsub.close()

            if self.client:
                await self.client.close()

            logger.info("Redis connection closed")

        except Exception as e:
            logger.error(f"Error during Redis disconnect: {e}")

    async def check_connection(self) -> bool:
        """接続状態をチェック"""
        try:
            if not self.client:
                return False

            # ping でヘルスチェック
            await self.client.ping()

            # pub/sub接続確認
            if self.pubsub and self.pubsub.connection:
                # メッセージが受信可能かテスト
                await self.client.publish("rakuten_monitor_healthcheck", "ping")
                return True

            return False

        except Exception as e:
            logger.warning(f"Redis connection check failed: {e}")
            return False

    async def reconnect(self) -> bool:
        """再接続を試行"""
        logger.info("Attempting Redis reconnection...")

        # 既存接続を切断
        await self.disconnect()

        # 再接続
        return await self.connect()

    async def start_watchdog(self):
        """Watchdog監視を開始"""
        self.is_running = True
        logger.info(f"Redis Watchdog started (interval: {self.watchdog_interval}s)")

        # 初回接続
        if not await self.connect():
            logger.error("Initial Redis connection failed")
            return

        while self.is_running:
            try:
                await asyncio.sleep(self.watchdog_interval)

                # 接続状態確認
                if not await self.check_connection():
                    logger.warning("Redis connection lost, attempting reconnection...")

                    # 再接続試行
                    if await self.reconnect():
                        logger.info("Redis reconnection successful")
                    else:
                        logger.error("Redis reconnection failed")
                else:
                    logger.debug("Redis connection healthy")

            except asyncio.CancelledError:
                logger.info("Redis Watchdog cancelled")
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                await asyncio.sleep(5)  # エラー時は短い間隔で再試行

    async def stop_watchdog(self):
        """Watchdog監視を停止"""
        self.is_running = False
        await self.disconnect()
        logger.info("Redis Watchdog stopped")

    async def publish_message(self, channel: str, message: str) -> bool:
        """メッセージをpublish"""
        try:
            if not self.client:
                return False

            await self.client.publish(channel, message)
            return True

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False

    async def get_message(self) -> Optional[dict]:
        """メッセージを受信"""
        try:
            if not self.pubsub:
                return None

            message = await self.pubsub.get_message(ignore_subscribe_messages=True)
            return message

        except Exception as e:
            logger.error(f"Failed to get message: {e}")
            return None


# グローバルインスタンス
redis_watchdog = RedisWatchdog()


async def main():
    """テスト実行"""
    logging.basicConfig(level=logging.INFO)

    try:
        # Watchdog開始
        watchdog_task = asyncio.create_task(redis_watchdog.start_watchdog())

        # メッセージ送信テスト
        await asyncio.sleep(2)
        await redis_watchdog.publish_message("rakuten_monitor", "test_message")

        # しばらく実行
        await asyncio.sleep(60)

    except KeyboardInterrupt:
        logger.info("Stopping Redis Watchdog...")
    finally:
        await redis_watchdog.stop_watchdog()
        if "watchdog_task" in locals():
            watchdog_task.cancel()
            try:
                await watchdog_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
