"""YouTube Analytics Batch - Entry Point."""

import argparse
import logging
import os
import sys
from pathlib import Path

from fetch.youtube import fetch_video, fetch_comments
from sentiment.analyzer import classify_comments
from aggregate.summarizer import aggregate_video

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


def process_video(video_id: str, comment_limit: int) -> dict | None:
    """
    Process a single video.

    Args:
        video_id: YouTube video ID
        comment_limit: Number of comments to fetch

    Returns:
        Processed data dict or None if failed
    """
    logger.info(f'動画を処理中: {video_id}')

    try:
        video = fetch_video(video_id)
        if not video:
            logger.error(f'動画の取得に失敗しました: {video_id}')
            return None

        comments = fetch_comments(video_id, comment_limit)
        comments = classify_comments(comments)

        # Aggregate
        aggregate_video(video, comments)

        return {**video, 'comments': comments}

    except Exception as e:
        logger.error(f'動画処理中にエラーが発生しました {video_id}: {e}')
        return None


def main(video_ids: list[str], comment_limit: int) -> None:
    """
    Batch processing entry point.

    Args:
        video_ids: List of YouTube video IDs to process
        comment_limit: Number of comments to fetch per video
    """
    logger.info(f'バッチ処理を開始します: {len(video_ids)}件の動画')
    logger.info(f'コメント取得上限: {comment_limit}件')

    success_count = 0
    fail_count = 0

    for video_id in video_ids:
        try:
            result = process_video(video_id, comment_limit)
            if result:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f'動画 {video_id} の処理中に予期しないエラーが発生しました: {e}')
            fail_count += 1

    logger.info(f'バッチ処理完了: 成功 {success_count}件, 失敗 {fail_count}件')


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

    args = parser.parse_args()

    # Parse video IDs
    video_ids = []
    if args.video_id:
        video_ids.append(args.video_id)
    if args.video_ids:
        video_ids.extend([v.strip() for v in args.video_ids.split(',') if v.strip()])

    if not video_ids:
        parser.error('At least one video ID is required (--video-id or --video-ids)')

    main(video_ids, args.comment_limit)
