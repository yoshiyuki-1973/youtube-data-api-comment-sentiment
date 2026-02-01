"""Pytest configuration and shared fixtures."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import torch


@pytest.fixture
def mock_youtube_api():
    """YouTube API mock fixture."""
    with patch('fetch.youtube.build') as mock_build:
        mock_api = MagicMock()
        mock_build.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_sentiment_models():
    """
    Mock sentiment analysis models to avoid loading heavy ML models in tests.
    Returns predictable sentiment scores for testing.
    """
    def create_mock_model_output(num_labels=3):
        """Create mock model output tensor."""
        if num_labels == 3:
            # 3-class model: negative, neutral, positive
            logits = torch.tensor([[0.1, 0.2, 0.7]])  # High positive
        else:
            # 2-class model: positive, negative
            logits = torch.tensor([[0.8, 0.2]])  # High positive
        return MagicMock(logits=logits)

    mock_ja_model_1 = MagicMock()
    mock_ja_model_1.return_value = create_mock_model_output(3)
    mock_ja_model_1.config.id2label = {0: 'negative', 1: 'neutral', 2: 'positive'}

    mock_ja_model_2 = MagicMock()
    mock_ja_model_2.return_value = create_mock_model_output(2)
    mock_ja_model_2.config.id2label = {0: 'ポジティブ', 1: 'ネガティブ'}

    mock_multi_model = MagicMock()
    mock_multi_model.return_value = create_mock_model_output(3)
    mock_multi_model.config.id2label = {0: 'negative', 1: 'neutral', 2: 'positive'}

    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {'input_ids': torch.tensor([[1, 2, 3]]), 'attention_mask': torch.tensor([[1, 1, 1]])}

    with patch('sentiment.analyzer._ja_model_1', mock_ja_model_1), \
         patch('sentiment.analyzer._ja_tokenizer_1', mock_tokenizer), \
         patch('sentiment.analyzer._ja_id2label_1', {0: 'negative', 1: 'neutral', 2: 'positive'}), \
         patch('sentiment.analyzer._ja_model_2', mock_ja_model_2), \
         patch('sentiment.analyzer._ja_tokenizer_2', mock_tokenizer), \
         patch('sentiment.analyzer._ja_id2label_2', {0: 'ポジティブ', 1: 'ネガティブ'}), \
         patch('sentiment.analyzer._multi_model', mock_multi_model), \
         patch('sentiment.analyzer._multi_tokenizer', mock_tokenizer), \
         patch('sentiment.analyzer._multi_id2label', {0: 'negative', 1: 'neutral', 2: 'positive'}), \
         patch('sentiment.analyzer.load_models'):
        yield {
            'ja_model_1': mock_ja_model_1,
            'ja_model_2': mock_ja_model_2,
            'multi_model': mock_multi_model,
            'tokenizer': mock_tokenizer
        }


@pytest.fixture
def mock_sentiment_classify():
    """
    Simple mock for classify_comments that returns predictable results.
    Use this when you don't need to test model behavior.
    """
    def mock_classify(comments):
        for comment in comments:
            text = comment.get('text', '').lower()
            # Simple rule-based mock classification
            if any(word in text for word in ['最高', '素晴らしい', '面白い', 'good', 'great']):
                comment['sentiment'] = {'positive': 0.8, 'negative': 0.1, 'neutral': 0.1, 'language': 'ja'}
            elif any(word in text for word in ['つまらない', 'ひどい', '最悪', 'bad', 'terrible']):
                comment['sentiment'] = {'positive': 0.1, 'negative': 0.8, 'neutral': 0.1, 'language': 'ja'}
            else:
                comment['sentiment'] = {'positive': 0.33, 'negative': 0.33, 'neutral': 0.34, 'language': 'ja'}
        return comments

    with patch('sentiment.analyzer.classify_comments', side_effect=mock_classify) as mock:
        yield mock


@pytest.fixture
def mock_db_connection():
    """DB connection mock fixture."""
    with patch('repository.mysql.get_connection') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.is_connected.return_value = True
        yield {'connection': mock_conn, 'cursor': mock_cursor}


@pytest.fixture
def sample_video():
    """Sample video data."""
    return {
        'video_id': 'dQw4w9WgXcQ',
        'title': 'Test Video',
        'channel_id': 'UC38IQsAvIsxxjztdMZQtwHA',
        'channel_title': 'Test Channel',
        'published_at': '2025-01-01T00:00:00Z',
        'view_count': 1000000,
        'like_count': 50000,
        'comment_count': 10000,
        'fetched_at': '2025-01-21T10:00:00'
    }


@pytest.fixture
def sample_comments():
    """Sample comments data."""
    return [
        {'comment_id': 'c1', 'author': 'User1', 'text': '最高！とても面白かった', 'like_count': 100, 'published_at': '2025-01-01T00:00:00Z'},
        {'comment_id': 'c2', 'author': 'User2', 'text': 'つまらない、時間の無駄', 'like_count': 50, 'published_at': '2025-01-01T00:00:00Z'},
        {'comment_id': 'c3', 'author': 'User3', 'text': '動画を見ました', 'like_count': 10, 'published_at': '2025-01-01T00:00:00Z'},
        {'comment_id': 'c4', 'author': 'User4', 'text': '素晴らしい内容でした！', 'like_count': 80, 'published_at': '2025-01-01T00:00:00Z'},
        {'comment_id': 'c5', 'author': 'User5', 'text': 'ひどい動画だ', 'like_count': 20, 'published_at': '2025-01-01T00:00:00Z'},
    ]


@pytest.fixture
def sample_classified_comments():
    """Sample comments with sentiment."""
    return [
        {'comment_id': 'c1', 'text': '最高！', 'sentiment': {'positive': 0.9, 'negative': 0.05, 'neutral': 0.05}},
        {'comment_id': 'c2', 'text': 'つまらない', 'sentiment': {'positive': 0.1, 'negative': 0.8, 'neutral': 0.1}},
        {'comment_id': 'c3', 'text': '普通', 'sentiment': {'positive': 0.2, 'negative': 0.2, 'neutral': 0.6}},
        {'comment_id': 'c4', 'text': '素晴らしい', 'sentiment': {'positive': 0.95, 'negative': 0.03, 'neutral': 0.02}},
        {'comment_id': 'c5', 'text': 'ひどい', 'sentiment': {'positive': 0.05, 'negative': 0.9, 'neutral': 0.05}},
    ]


def load_fixture(name: str) -> dict:
    """Load fixture JSON file."""
    path = Path(__file__).parent / 'fixtures' / name
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}
