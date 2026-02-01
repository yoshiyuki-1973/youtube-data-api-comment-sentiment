"""YouTube Analytics Batch - Entry Point."""

import argparse
import logging
import os
import sys
from pathlib import Path

from fetch.youtube import fetch_video, fetch_comments
from sentiment.analyzer import classify_comments
from aggregate.summarizer import aggregate_video
from repository.mysql import save_video, save_summary, close_connection
from utils.cache import save_json, load_json

# Ensure log directory exists before configuring file handlers
LOG_DIR = Path(os.environ.get('LOG_DIR', '/app/logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'app.log', encoding='utf-8'),
    ]
)

# Error-only file handler
error_handler = logging.FileHandler(LOG_DIR / 'error.log', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
logging.getLogger().addHandler(error_handler)

logger = logging.getLogger(__name__)


def process_video(video_id: str, comment_limit: int, use_cache: bool = True) -> dict | None:
    """
    Process a single video.

    Args:
        video_id: YouTube video ID
        comment_limit: Number of comments to fetch
        use_cache: Whether to use cached JSON data

    Returns:
        Processed data dict or None if failed
    """
    logger.info(f'動画を処理中: {video_id}')

    # Try to load from cache
    if use_cache:
        cached_data = load_json(video_id)
        if cached_data:
            logger.info(f'キャッシュデータを使用します: {video_id}')
            # Validate sentiment data format
            comments = cached_data.get('comments', [])
            needs_reclassification = False
            
            for comment in comments:
                sentiment = comment.get('sentiment')
                # Check if sentiment is valid dict with required keys
                if not isinstance(sentiment, dict) or \
                   not all(key in sentiment for key in ['positive', 'negative', 'neutral']):
                    needs_reclassification = True
                    logger.warning(f'キャッシュデータのsentiment形式が無効です。再分類します。')
                    break
            
            # Re-classify if sentiment data is invalid
            if needs_reclassification:
                comments = classify_comments(comments)
                cached_data['comments'] = comments
                save_json(video_id, cached_data)  # Update cache
            
            video = {k: v for k, v in cached_data.items() if k != 'comments'}
            summary = aggregate_video(video, comments)
            save_video(video)
            save_summary(summary)
            return cached_data

    # Fetch from API
    try:
        video = fetch_video(video_id)
        if not video:
            logger.error(f'動画の取得に失敗しました: {video_id}')
            return None

        comments = fetch_comments(video_id, comment_limit)
        comments = classify_comments(comments)

        # Combine video and comments data
        data = {**video, 'comments': comments}

        # Save to JSON
        save_json(video_id, data)

        # Aggregate and save to DB
        summary = aggregate_video(video, comments)
        save_video(video)
        save_summary(summary)

        return data

    except Exception as e:
        logger.error(f'動画処理中にエラーが発生しました {video_id}: {e}')
        return None


def main(video_ids: list[str], comment_limit: int, use_cache: bool = True) -> None:
    """
    Batch processing entry point.

    Args:
        video_ids: List of YouTube video IDs to process
        comment_limit: Number of comments to fetch per video
        use_cache: Whether to load/save cached JSON
    """
    logger.info(f'バッチ処理を開始します: {len(video_ids)}件の動画')
    logger.info(f'コメント取得上限: {comment_limit}件')
    logger.info(f'キャッシュ使用: {use_cache}')

    success_count = 0
    fail_count = 0

    for video_id in video_ids:
        try:
            result = process_video(video_id, comment_limit, use_cache=use_cache)
            if result:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f'動画 {video_id} の処理中に予期しないエラーが発生しました: {e}')
            fail_count += 1

    logger.info(f'バッチ処理完了: 成功 {success_count}件, 失敗 {fail_count}件')

    # Close DB connection
    close_connection()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YouTube Analytics Batch')
    parser.add_argument('--video-id', type=str, help='Single video ID to process')
    parser.add_argument('--video-ids', type=str, help='Comma-separated video IDs')
    parser.add_argument(
        '--comment-limit',
        type=int,
        default=int(os.environ.get('COMMENT_LIMIT', 10)),
        help='Number of comments to fetch per video (default: 10)'
    )
    parser.add_argument('--no-cache', action='store_true', help='Disable JSON cache')

    args = parser.parse_args()

    # Parse video IDs
    video_ids = []
    if args.video_id:
        video_ids.append(args.video_id)
    if args.video_ids:
        video_ids.extend([v.strip() for v in args.video_ids.split(',') if v.strip()])

    if not video_ids:
        parser.error('At least one video ID is required (--video-id or --video-ids)')

    use_cache = not args.no_cache

    main(video_ids, args.comment_limit, use_cache=use_cache)
