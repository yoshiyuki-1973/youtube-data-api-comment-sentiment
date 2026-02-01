"""MySQL repository module."""

import datetime as dt_module
import logging
import os
from datetime import datetime

import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool

from utils.text import truncate_string

logger = logging.getLogger(__name__)

# Database connection pool (lazy initialization)
_connection_pool = None


def _get_connection_pool():
    """Get or create MySQL connection pool."""
    global _connection_pool
    if _connection_pool is None:
        try:
            # Parse pool_size with validation
            try:
                pool_size = int(os.environ.get('MYSQL_POOL_SIZE', 5))
            except (ValueError, TypeError):
                logger.warning('MYSQL_POOL_SIZE設定が無効です。デフォルト値5を使用します。')
                pool_size = 5

            # Parse port with validation
            try:
                port = int(os.environ.get('MYSQL_PORT', 3306))
            except (ValueError, TypeError):
                logger.warning('MYSQL_PORT設定が無効です。デフォルト値3306を使用します。')
                port = 3306

            pool_name = os.environ.get('MYSQL_POOL_NAME', 'youtube_analytics_pool')
            _connection_pool = MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=pool_size,
                host=os.environ.get('MYSQL_HOST', 'mysql'),
                port=port,
                database=os.environ.get('MYSQL_DATABASE', 'youtube_analytics'),
                user=os.environ.get('MYSQL_USER', 'app_user'),
                password=os.environ.get('MYSQL_PASSWORD', ''),
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            logger.info(f'MySQL接続プールを作成しました (pool_name={pool_name}, pool_size={pool_size})')
        except Error as e:
            logger.error(f'MySQL接続プール作成エラー: {e}')
            raise
    return _connection_pool


def get_connection():
    """Get a connection from the pool."""
    try:
        pool = _get_connection_pool()
        connection = pool.get_connection()
        logger.debug('MySQL接続をプールから取得しました')
        return connection
    except Error as e:
        logger.error(f'MySQL接続取得エラー: {e}')
        raise


def close_connection() -> None:
    """Close all connections in the pool (called at application shutdown)."""
    global _connection_pool
    if _connection_pool:
        # Connection pool automatically manages connections
        # This function is kept for compatibility but doesn't need to do anything
        logger.info('MySQL接続プールは自動管理されます')


def _parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string."""
    if not dt_str:
        return None
    try:
        # Handle various ISO 8601 formats
        # Replace Z with +00:00 for UTC timezone
        dt_str = dt_str.replace('Z', '+00:00')
        
        # Remove microseconds but keep timezone
        if '.' in dt_str:
            # Split on dot, keep everything after the seconds
            parts = dt_str.split('.')
            # Check if there's timezone info after microseconds
            if '+' in parts[1] or '-' in parts[1]:
                tz_char = '+' if '+' in parts[1] else '-'
                tz_part = tz_char + parts[1].split(tz_char)[1]
                dt_str = parts[0] + tz_part
            else:
                dt_str = parts[0]
        
        # Parse with timezone information preserved
        parsed_dt = datetime.fromisoformat(dt_str)
        # Convert to naive datetime in UTC for MySQL compatibility
        if parsed_dt.tzinfo is not None:
            parsed_dt = parsed_dt.astimezone(dt_module.timezone.utc).replace(tzinfo=None)
        return parsed_dt
    except (ValueError, AttributeError) as e:
        logger.warning(f'日時パースエラー: {dt_str} - {e}')
        return None


def save_video(video: dict) -> None:
    """
    Save video information to MySQL (UPSERT).

    Args:
        video: Video information dict
    """
    video_id = video.get('video_id')
    logger.info(f'Saving video: {video_id}')

    conn = get_connection()
    cursor = conn.cursor()

    try:
        sql = """
            INSERT INTO videos (
                video_id, title, channel_id, channel_title,
                published_at, view_count, like_count, comment_count, fetched_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                channel_title = VALUES(channel_title),
                view_count = VALUES(view_count),
                like_count = VALUES(like_count),
                comment_count = VALUES(comment_count),
                fetched_at = VALUES(fetched_at)
        """

        values = (
            video_id,
            truncate_string(video.get('title', ''), 255),
            video.get('channel_id', ''),
            truncate_string(video.get('channel_title', ''), 255),
            _parse_datetime(video.get('published_at')),
            video.get('view_count', 0),
            video.get('like_count', 0),
            video.get('comment_count', 0),
            _parse_datetime(video.get('fetched_at')) or datetime.now()
        )

        cursor.execute(sql, values)
        conn.commit()
        logger.info(f'動画情報を保存しました: {video_id}')

    except Error as e:
        logger.error(f'動画保存エラー {video_id}: {e}')
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()  # Return connection to pool


def save_summary(summary: dict) -> None:
    """
    Save sentiment analysis summary to MySQL (UPSERT).

    Args:
        summary: Summary dict from aggregate_video()
    """
    video_id = summary.get('video_id')
    logger.info(f'Saving summary for video: {video_id}')

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Delete existing summary for this video
        cursor.execute(
            'DELETE FROM video_comment_summary WHERE video_id = %s',
            (video_id,)
        )

        sql = """
            INSERT INTO video_comment_summary (
                video_id, total_comments, positive_count, negative_count,
                other_count, positive_ratio, negative_ratio, analyzed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        values = (
            video_id,
            summary.get('total_comments', 0),
            summary.get('positive_count', 0),
            summary.get('negative_count', 0),
            summary.get('other_count', 0),
            summary.get('positive_ratio', 0.0),
            summary.get('negative_ratio', 0.0),
            _parse_datetime(summary.get('analyzed_at')) or datetime.now()
        )

        cursor.execute(sql, values)
        conn.commit()
        logger.info(f'感情分析サマリーを保存しました: {video_id}')

    except Error as e:
        logger.error(f'サマリー保存エラー {video_id}: {e}')
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()  # Return connection to pool


def get_video(video_id: str) -> dict | None:
    """
    Get video information from MySQL.

    Args:
        video_id: YouTube video ID

    Returns:
        Video dict or None if not found
    """
    logger.info(f'Getting video from cache: {video_id}')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        sql = """
            SELECT video_id, title, channel_id, channel_title,
                   published_at, view_count, like_count, comment_count, fetched_at
            FROM videos
            WHERE video_id = %s
        """
        cursor.execute(sql, (video_id,))
        result = cursor.fetchone()

        if result:
            # Convert datetime to ISO string
            if result.get('published_at'):
                result['published_at'] = result['published_at'].isoformat()
            if result.get('fetched_at'):
                result['fetched_at'] = result['fetched_at'].isoformat()
            logger.info(f'キャッシュから動画情報を取得: {video_id}')
            return result

        logger.info(f'キャッシュに動画情報なし: {video_id}')
        return None

    except Error as e:
        logger.error(f'動画取得エラー {video_id}: {e}')
        return None
    finally:
        cursor.close()
        conn.close()


def get_summary(video_id: str) -> dict | None:
    """
    Get sentiment analysis summary from MySQL.

    Args:
        video_id: YouTube video ID

    Returns:
        Summary dict or None if not found
    """
    logger.info(f'Getting summary from cache: {video_id}')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        sql = """
            SELECT video_id, total_comments, positive_count, negative_count,
                   other_count, positive_ratio, negative_ratio, analyzed_at
            FROM video_comment_summary
            WHERE video_id = %s
        """
        cursor.execute(sql, (video_id,))
        result = cursor.fetchone()

        if result:
            # Convert datetime to ISO string
            if result.get('analyzed_at'):
                result['analyzed_at'] = result['analyzed_at'].isoformat()
            
            # Add score fields for compatibility (ensure neutral_score is not negative)
            pos_ratio = result.get('positive_ratio', 0.0)
            neg_ratio = result.get('negative_ratio', 0.0)
            result['positive_score'] = pos_ratio
            result['negative_score'] = neg_ratio
            result['neutral_score'] = max(0.0, 1.0 - pos_ratio - neg_ratio)
            
            logger.info(f'キャッシュからサマリーを取得: {video_id}')
            return result

        logger.info(f'キャッシュにサマリーなし: {video_id}')
        return None

    except Error as e:
        logger.error(f'サマリー取得エラー {video_id}: {e}')
        return None
    finally:
        cursor.close()
        conn.close()
