"""Test save_video truncation with emoji and multi-byte characters."""

import pytest
from unittest.mock import patch, MagicMock

from app.repository.mysql import save_video


# executeに渡される値のインデックス
# video_id(0), title(1), channel_id(2), channel_title(3), published_at(4),
# view_count(5), like_count(6), comment_count(7), fetched_at(8) の順
_INDEX_TITLE = 1
_INDEX_CHANNEL_TITLE = 3


@pytest.fixture
def mock_db():
    """DBモックを提供するフィクスチャ"""
    with patch('app.repository.mysql.get_connection') as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_cursor


def _extract_value_from_call(mock_cursor, index):
    """executeの引数から指定インデックスの値を抽出"""
    call_args = mock_cursor.execute.call_args
    values = call_args[0][1]
    return values[index]


def _assert_valid_utf8(text, field_name):
    """文字列が有効なUTF-8であることを検証"""
    try:
        text.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError:
        pytest.fail(f"{field_name}: 無効なUTF-8文字列")


@pytest.mark.parametrize("title", [
    pytest.param('A' * 300, id="ASCII_300文字"),
    pytest.param('😀' * 300, id="絵文字のみ_300文字"),
    pytest.param('日本語のタイトル😀です' * 50, id="漢字と絵文字混合"),
    pytest.param('B' * 255, id="ちょうど255文字"),
    pytest.param('', id="空文字列"),
])
def test_truncate_title(mock_db, title):
    """タイトルが255文字以内に切り詰められることを検証"""
    video = {
        'video_id': 'test1',
        'title': title,
        'channel_id': 'UC123',
        'fetched_at': '2025-01-21T10:00:00'
    }

    save_video(video)

    assert mock_db.execute.called, "execute()が呼ばれていない"
    truncated_title = _extract_value_from_call(mock_db, _INDEX_TITLE)

    assert len(truncated_title) <= 255, f"文字数が255を超えている ({len(truncated_title)})"
    _assert_valid_utf8(truncated_title, "title")


@pytest.mark.parametrize("channel_title", [
    pytest.param('C' * 300, id="ASCII_300文字"),
    pytest.param('🎬チャンネル名' * 100, id="絵文字と日本語混合"),
])
def test_truncate_channel_title(mock_db, channel_title):
    """channel_titleも255文字以内に切り詰められることを検証"""
    video = {
        'video_id': 'test2',
        'title': 'Normal title',
        'channel_id': 'UC123',
        'channel_title': channel_title,
        'fetched_at': '2025-01-21T10:00:00'
    }

    save_video(video)

    assert mock_db.execute.called, "execute()が呼ばれていない"
    truncated = _extract_value_from_call(mock_db, _INDEX_CHANNEL_TITLE)

    assert len(truncated) <= 255, f"channel_title: 文字数が255を超えている ({len(truncated)})"
    _assert_valid_utf8(truncated, "channel_title")


def test_short_title_not_truncated(mock_db):
    """255文字以下のタイトルは切り詰められないことを検証"""
    original_title = '短いタイトル😀'
    video = {
        'video_id': 'test3',
        'title': original_title,
        'channel_id': 'UC123',
        'fetched_at': '2025-01-21T10:00:00'
    }

    save_video(video)

    assert mock_db.execute.called
    title = _extract_value_from_call(mock_db, _INDEX_TITLE)

    assert title == original_title, "短いタイトルが変更されている"
