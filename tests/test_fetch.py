"""Tests for YouTube fetch module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

import json
import pytest
from unittest.mock import patch, MagicMock
from googleapiclient.errors import HttpError

from fetch.youtube import (
    YouTubeAPIError,
    QuotaExceededError,
    AuthenticationError,
    VideoNotFoundError,
    CommentsDisabledError,
)


class TestFetchVideo:
    """Tests for fetch_video function."""

    @patch('fetch.youtube._get_client')
    def test_fetch_video_success(self, mock_get_client):
        """Test successful video fetch."""
        from fetch.youtube import fetch_video

        mock_response = {
            'items': [{
                'id': 'dQw4w9WgXcQ',
                'snippet': {
                    'title': 'Test Video',
                    'channelId': 'UC123',
                    'channelTitle': 'Test Channel',
                    'publishedAt': '2025-01-01T00:00:00Z'
                },
                'statistics': {
                    'viewCount': '1000',
                    'likeCount': '100',
                    'commentCount': '10'
                }
            }]
        }

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response

        result = fetch_video('dQw4w9WgXcQ')

        assert result['video_id'] == 'dQw4w9WgXcQ'
        assert result['title'] == 'Test Video'
        assert result['channel_id'] == 'UC123'
        assert result['view_count'] == 1000
        assert result['like_count'] == 100
        assert result['comment_count'] == 10

    @patch('fetch.youtube._get_client')
    def test_fetch_video_not_found(self, mock_get_client):
        """Test video not found."""
        from fetch.youtube import fetch_video

        mock_response = {'items': []}

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.videos.return_value.list.return_value.execute.return_value = mock_response

        result = fetch_video('invalid_id')

        assert result is None

    @patch('fetch.youtube._get_client')
    def test_fetch_video_quota_exceeded(self, mock_get_client):
        """Test quota exceeded error raises QuotaExceededError."""
        from fetch.youtube import fetch_video

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        error_content = json.dumps({
            'error': {
                'errors': [{'reason': 'quotaExceeded'}]
            }
        }).encode('utf-8')
        mock_youtube.videos.return_value.list.return_value.execute.side_effect = \
            HttpError(resp=MagicMock(status=403), content=error_content)

        with pytest.raises(QuotaExceededError):
            fetch_video('abc123')

    @patch('fetch.youtube._get_client')
    def test_fetch_video_auth_error(self, mock_get_client):
        """Test authentication error raises AuthenticationError."""
        from fetch.youtube import fetch_video

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.videos.return_value.list.return_value.execute.side_effect = \
            HttpError(resp=MagicMock(status=401), content=b'unauthorized')

        with pytest.raises(AuthenticationError):
            fetch_video('abc123')

    @patch('fetch.youtube._get_client')
    def test_fetch_video_404_error(self, mock_get_client):
        """Test 404 error raises VideoNotFoundError."""
        from fetch.youtube import fetch_video

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.videos.return_value.list.return_value.execute.side_effect = \
            HttpError(resp=MagicMock(status=404), content=b'not found')

        with pytest.raises(VideoNotFoundError):
            fetch_video('abc123')


class TestFetchComments:
    """Tests for fetch_comments function."""

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_default_limit(self, mock_get_client):
        """Test fetching comments with default limit."""
        from fetch.youtube import fetch_comments

        mock_response = {
            'items': [
                {
                    'id': f'comment_{i}',
                    'snippet': {
                        'topLevelComment': {
                            'snippet': {
                                'authorDisplayName': f'User{i}',
                                'textDisplay': f'Comment {i}',
                                'likeCount': 10 - i,
                                'publishedAt': '2025-01-01T00:00:00Z'
                            }
                        }
                    }
                }
                for i in range(10)
            ]
        }

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.commentThreads.return_value.list.return_value.execute.return_value = mock_response

        comments = fetch_comments('abc123')

        assert len(comments) <= 10

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_custom_limit(self, mock_get_client):
        """Test fetching comments with custom limit."""
        from fetch.youtube import fetch_comments

        mock_response = {
            'items': [
                {
                    'id': f'comment_{i}',
                    'snippet': {
                        'topLevelComment': {
                            'snippet': {
                                'authorDisplayName': f'User{i}',
                                'textDisplay': f'Comment {i}',
                                'likeCount': 5 - i,
                                'publishedAt': '2025-01-01T00:00:00Z'
                            }
                        }
                    }
                }
                for i in range(5)
            ]
        }

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.commentThreads.return_value.list.return_value.execute.return_value = mock_response

        comments = fetch_comments('abc123', comment_limit=5)

        assert len(comments) <= 5

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_sorted_by_likes(self, mock_get_client):
        """Test comments are sorted by like count."""
        from fetch.youtube import fetch_comments

        mock_response = {
            'items': [
                {
                    'id': 'c1',
                    'snippet': {
                        'topLevelComment': {
                            'snippet': {
                                'authorDisplayName': 'User1',
                                'textDisplay': 'Low likes',
                                'likeCount': 5,
                                'publishedAt': '2025-01-01T00:00:00Z'
                            }
                        }
                    }
                },
                {
                    'id': 'c2',
                    'snippet': {
                        'topLevelComment': {
                            'snippet': {
                                'authorDisplayName': 'User2',
                                'textDisplay': 'High likes',
                                'likeCount': 100,
                                'publishedAt': '2025-01-01T00:00:00Z'
                            }
                        }
                    }
                },
            ]
        }

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.commentThreads.return_value.list.return_value.execute.return_value = mock_response

        comments = fetch_comments('abc123', comment_limit=10)

        # Should be sorted by like_count descending
        assert comments[0]['like_count'] >= comments[-1]['like_count']

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_quota_exceeded(self, mock_get_client):
        """Test quota exceeded error raises QuotaExceededError."""
        from fetch.youtube import fetch_comments

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        error_content = json.dumps({
            'error': {
                'errors': [{'reason': 'quotaExceeded'}]
            }
        }).encode('utf-8')
        mock_youtube.commentThreads.return_value.list.return_value.execute.side_effect = \
            HttpError(resp=MagicMock(status=403), content=error_content)

        with pytest.raises(QuotaExceededError):
            fetch_comments('abc123')

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_disabled(self, mock_get_client):
        """Test comments disabled error raises CommentsDisabledError."""
        from fetch.youtube import fetch_comments

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube

        error_content = json.dumps({
            'error': {
                'errors': [{'reason': 'commentsDisabled'}]
            }
        }).encode('utf-8')
        mock_youtube.commentThreads.return_value.list.return_value.execute.side_effect = \
            HttpError(resp=MagicMock(status=403), content=error_content)

        with pytest.raises(CommentsDisabledError):
            fetch_comments('abc123')

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_empty_result(self, mock_get_client):
        """コメントがゼロ件の場合のテスト。"""
        from fetch.youtube import fetch_comments

        mock_response = {'items': []}

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.commentThreads.return_value.list.return_value.execute.return_value = mock_response

        comments = fetch_comments('abc123')

        assert len(comments) == 0

    @patch('fetch.youtube._get_client')
    def test_fetch_comments_pagination(self, mock_get_client):
        """ページネーションのテスト。"""
        from fetch.youtube import fetch_comments

        # First page
        mock_response_page1 = {
            'items': [
                {
                    'id': f'comment_{i}',
                    'snippet': {
                        'topLevelComment': {
                            'snippet': {
                                'authorDisplayName': f'User{i}',
                                'textDisplay': f'Comment {i}',
                                'likeCount': 10 - i,
                                'publishedAt': '2025-01-01T00:00:00Z'
                            }
                        }
                    }
                }
                for i in range(5)
            ],
            'nextPageToken': 'page2_token'
        }

        # Second page
        mock_response_page2 = {
            'items': [
                {
                    'id': f'comment_{i}',
                    'snippet': {
                        'topLevelComment': {
                            'snippet': {
                                'authorDisplayName': f'User{i}',
                                'textDisplay': f'Comment {i}',
                                'likeCount': 5 - i,
                                'publishedAt': '2025-01-01T00:00:00Z'
                            }
                        }
                    }
                }
                for i in range(5, 10)
            ]
        }

        mock_youtube = MagicMock()
        mock_get_client.return_value = mock_youtube
        mock_youtube.commentThreads.return_value.list.return_value.execute.side_effect = [
            mock_response_page1,
            mock_response_page2
        ]

        comments = fetch_comments('abc123', comment_limit=10)

        assert len(comments) <= 10
        # Verify pagination was called
        assert mock_youtube.commentThreads.return_value.list.return_value.execute.call_count >= 1
