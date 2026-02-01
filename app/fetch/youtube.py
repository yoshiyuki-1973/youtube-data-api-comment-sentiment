"""YouTube Data API client module."""

import logging
import os
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Constants (configurable via environment variables)
try:
    API_MAX_RESULTS = int(os.environ.get('API_MAX_RESULTS', 100))
except (ValueError, TypeError):
    logger.warning('API_MAX_RESULTS設定が無効です。デフォルト値100を使用します。')
    API_MAX_RESULTS = 100

try:
    COMMENT_FETCH_MULTIPLIER = int(os.environ.get('COMMENT_FETCH_MULTIPLIER', 2))
except (ValueError, TypeError):
    logger.warning('COMMENT_FETCH_MULTIPLIER設定が無効です。デフォルト値2を使用します。')
    COMMENT_FETCH_MULTIPLIER = 2


class YouTubeAPIError(Exception):
    """Base exception for YouTube API errors."""
    pass


class QuotaExceededError(YouTubeAPIError):
    """Raised when API quota is exceeded."""
    pass


class AuthenticationError(YouTubeAPIError):
    """Raised when API key is invalid or unauthorized."""
    pass


class VideoNotFoundError(YouTubeAPIError):
    """Raised when video is not found or private."""
    pass


class CommentsDisabledError(YouTubeAPIError):
    """Raised when comments are disabled for the video."""
    pass


def _handle_http_error(e: HttpError, context: str) -> None:
    """
    Handle HttpError and raise appropriate custom exception.

    Args:
        e: The HttpError exception
        context: Description of the operation that failed

    Raises:
        QuotaExceededError: When API quota is exceeded (403 with quotaExceeded)
        AuthenticationError: When API key is invalid (401, 403 with other reasons)
        CommentsDisabledError: When comments are disabled (403 with commentsDisabled)
        VideoNotFoundError: When video is not found (404)
        YouTubeAPIError: For other API errors
    """
    status = e.resp.status
    error_reason = ''

    # Extract error reason from response
    try:
        import json
        error_content = json.loads(e.content.decode('utf-8'))
        errors = error_content.get('error', {}).get('errors', [])
        if errors:
            error_reason = errors[0].get('reason', '')
    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    if status == 401:
        logger.error(f'{context}: 認証エラー - APIキーが無効です')
        raise AuthenticationError(f'APIキーが無効です: {e}')

    elif status == 403:
        if error_reason == 'quotaExceeded':
            logger.error(f'{context}: APIクォータ超過')
            raise QuotaExceededError(f'YouTube APIのクォータを超過しました: {e}')
        elif error_reason == 'commentsDisabled':
            logger.warning(f'{context}: コメントが無効化されています')
            raise CommentsDisabledError(f'この動画ではコメントが無効化されています: {e}')
        else:
            logger.error(f'{context}: アクセス拒否 (reason: {error_reason})')
            raise AuthenticationError(f'アクセスが拒否されました: {e}')

    elif status == 404:
        logger.warning(f'{context}: 動画が見つかりません')
        raise VideoNotFoundError(f'動画が見つかりませんでした: {e}')

    else:
        logger.error(f'{context}: APIエラー (status: {status})')
        raise YouTubeAPIError(f'YouTube APIエラー: {e}')

# YouTube API client (lazy initialization)
_youtube_client = None


def _get_client():
    """Get or create YouTube API client."""
    global _youtube_client
    if _youtube_client is None:
        api_key = os.environ.get('YOUTUBE_API_KEY')
        if not api_key:
            raise RuntimeError('YOUTUBE_API_KEY environment variable is not set')
        _youtube_client = build('youtube', 'v3', developerKey=api_key)
    return _youtube_client


def fetch_video(video_id: str) -> dict | None:
    """
    Fetch video metadata from YouTube Data API.

    Args:
        video_id: YouTube video ID

    Returns:
        Video information dict, or None if not found
    """
    logger.info(f'動画情報を取得中: {video_id}')

    try:
        youtube = _get_client()
        response = youtube.videos().list(
            part='snippet,statistics',
            id=video_id
        ).execute()

        if not response.get('items'):
            logger.warning(f'動画が見つかりませんでした: {video_id}')
            return None

        item = response['items'][0]
        snippet = item['snippet']
        statistics = item.get('statistics', {})

        return {
            'video_id': item['id'],
            'title': snippet['title'],
            'channel_id': snippet['channelId'],
            'channel_title': snippet.get('channelTitle', ''),
            'published_at': snippet['publishedAt'],
            'view_count': int(statistics.get('viewCount', 0)),
            'like_count': int(statistics.get('likeCount', 0)),
            'comment_count': int(statistics.get('commentCount', 0)),
            'fetched_at': datetime.now().isoformat()
        }

    except HttpError as e:
        _handle_http_error(e, f'動画取得 {video_id}')


def fetch_comments(video_id: str, comment_limit: int = 10) -> list[dict]:
    """
    Fetch comments from YouTube Data API (sorted by like count).

    Args:
        video_id: YouTube video ID
        comment_limit: Number of comments to fetch (default: 10)

    Returns:
        List of comment dicts
    """
    logger.info(f'動画のコメントを{comment_limit}件取得中: {video_id}')

    try:
        youtube = _get_client()
        comments = []
        next_page_token = None

        # Note: YouTube API doesn't support sorting by like count directly
        # We fetch by relevance and then sort manually by like_count
        # For better performance, we fetch more comments than needed and sort
        fetch_limit = min(comment_limit * COMMENT_FETCH_MULTIPLIER, API_MAX_RESULTS)
        
        while len(comments) < fetch_limit:
            response = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                order='relevance',  # Use relevance as it often correlates with likes
                maxResults=min(API_MAX_RESULTS, fetch_limit - len(comments)),
                pageToken=next_page_token
            ).execute()

            for item in response.get('items', []):
                snippet = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'comment_id': item['id'],
                    'author': snippet.get('authorDisplayName', ''),
                    'text': snippet['textDisplay'],
                    'like_count': int(snippet.get('likeCount', 0)),
                    'published_at': snippet['publishedAt']
                })

                if len(comments) >= fetch_limit:
                    break

            next_page_token = response.get('nextPageToken')
            if not next_page_token or len(comments) >= fetch_limit:
                break

        # Sort by like count (descending)
        comments.sort(key=lambda x: x['like_count'], reverse=True)

        logger.info(f'コメントを{len(comments)}件取得しました: {video_id}')
        return comments[:comment_limit]

    except HttpError as e:
        _handle_http_error(e, f'コメント取得 {video_id}')
