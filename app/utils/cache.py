"""JSON cache utility module."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

JSON_OUTPUT_DIR = Path(os.environ.get('JSON_OUTPUT_DIR', '/app/data/json'))


def save_json(video_id: str, data: dict) -> bool:
    """
    Save data to JSON file.

    Args:
        video_id: YouTube video ID
        data: Data to save

    Returns:
        True if successful, False otherwise
    """
    try:
        JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = JSON_OUTPUT_DIR / f'{video_id}.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f'JSONを保存しました: {filepath}')
        return True
    except (OSError, IOError) as e:
        logger.error(f'JSON保存エラー: {video_id} - {e}')
        return False
    except (TypeError, ValueError) as e:
        logger.error(f'JSONシリアライズエラー: {video_id} - {e}')
        return False


def load_json(video_id: str) -> dict | None:
    """
    Load data from JSON file if exists.

    Args:
        video_id: YouTube video ID

    Returns:
        Loaded data or None if not found or on error
    """
    filepath = JSON_OUTPUT_DIR / f'{video_id}.json'
    if not filepath.exists():
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            logger.info(f'キャッシュされたJSONを読み込んでいます: {filepath}')
            return json.load(f)
    except (OSError, IOError) as e:
        logger.error(f'JSON読み込みエラー: {filepath} - {e}')
        return None
    except json.JSONDecodeError as e:
        logger.error(f'JSON解析エラー（ファイル破損の可能性）: {filepath} - {e}')
        return None
