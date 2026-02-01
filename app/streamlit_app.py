"""YouTube Analytics - Streamlit Web UI."""

import re
import logging
import sys
import os
from pathlib import Path

import streamlit as st
import pandas as pd

from fetch.youtube import (
    fetch_video,
    fetch_comments,
    QuotaExceededError,
    AuthenticationError,
    VideoNotFoundError,
    CommentsDisabledError,
)
from sentiment.analyzer import classify_comments
from aggregate.summarizer import aggregate_video
from repository.mysql import save_video, save_summary, get_video, get_summary
from utils.cache import save_json, load_json

# Configure logging for Streamlit
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="YouTube Comment Analyzer",
    page_icon="📊",
    layout="wide"
)


def extract_video_id(input_str: str) -> str | None:
    """
    Extract YouTube video ID from URL or direct ID.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    - VIDEO_ID (direct 11-character ID)

    Args:
        input_str: YouTube URL or video ID

    Returns:
        Video ID or None if invalid
    """
    input_str = input_str.strip()

    if not input_str:
        return None

    # Pattern for direct video ID (11 characters, alphanumeric + - _)
    direct_id_pattern = r'^[a-zA-Z0-9_-]{11}$'
    if re.match(direct_id_pattern, input_str):
        return input_str

    # Patterns for various YouTube URL formats
    url_patterns = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in url_patterns:
        match = re.search(pattern, input_str)
        if match:
            return match.group(1)

    return None


def get_comment_limit() -> int:
    """
    Get comment limit from environment variable.
    
    Returns:
        Comment limit (default: 10)
    """
    try:
        limit = int(os.environ.get('COMMENT_LIMIT', '10'))
        return max(1, min(limit, 100))  # 1-100の範囲に制限
    except (ValueError, TypeError):
        logger.warning('COMMENT_LIMIT設定が無効です。デフォルト値10を使用します。')
        return 10


def analyze_video(video_id: str, comment_limit: int, use_cache: bool = True) -> dict | None:
    """
    Analyze a YouTube video.

    Args:
        video_id: YouTube video ID
        comment_limit: Number of comments to fetch
        use_cache: Whether to use cached JSON data

    Returns:
        Analysis result dict or None if failed
    """
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
                    logger.warning('キャッシュデータのsentiment形式が無効です。再分類します。')
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
            return {
                'video': video,
                'comments': comments,
                'summary': summary
            }

    # Fetch video metadata
    video = fetch_video(video_id)
    if not video:
        return None

    # Fetch and classify comments
    comments = fetch_comments(video_id, comment_limit)
    comments = classify_comments(comments)

    # Aggregate results
    summary = aggregate_video(video, comments)

    # Save to JSON cache
    data = {**video, 'comments': comments}
    save_json(video_id, data)

    # Save to database
    save_video(video)
    save_summary(summary)

    return {
        'video': video,
        'comments': comments,
        'summary': summary
    }


def display_video_info(video: dict) -> None:
    """Display video information."""
    st.subheader("動画情報")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("再生回数", f"{video.get('view_count', 0):,}")
    with col2:
        st.metric("高評価数", f"{video.get('like_count', 0):,}")
    with col3:
        st.metric("コメント数", f"{video.get('comment_count', 0):,}")

    st.markdown(f"**タイトル**: {video.get('title', 'N/A')}")
    st.markdown(f"**チャンネル**: {video.get('channel_title', 'N/A')}")
    st.markdown(f"**公開日**: {video.get('published_at', 'N/A')}")


def display_sentiment_summary(summary: dict) -> None:
    """Display sentiment analysis summary."""
    st.subheader("感情分析結果")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("分析コメント数", summary.get('total_comments', 0))
    with col2:
        positive_score = summary.get('positive_score', 0)
        st.metric(
            "ポジティブ",
            f"{positive_score:.4f}",
        )
    with col3:
        negative_score = summary.get('negative_score', 0)
        st.metric(
            "ネガティブ",
            f"{negative_score:.4f}",
        )
    with col4:
        neutral_score = summary.get('neutral_score', 0)
        st.metric("ニュートラル", f"{neutral_score:.4f}")

    # Sentiment bar chart
    if summary.get('total_comments', 0) > 0:
        chart_data = pd.DataFrame({
            '感情': ['ポジティブ', 'ネガティブ', 'ニュートラル'],
            'スコア': [
                summary.get('positive_score', 0),
                summary.get('negative_score', 0),
                summary.get('neutral_score', 0)
            ]
        })
        st.bar_chart(chart_data.set_index('感情'))


def display_comments(comments: list) -> None:
    """Display analyzed comments."""
    st.subheader("コメント一覧")

    if not comments:
        st.info("コメントがありません")
        return

    # Sentiment filter
    sentiment_filter = st.selectbox(
        "感情でフィルタ",
        ["すべて", "ポジティブ優勢", "ネガティブ優勢", "ニュートラル優勢"]
    )

    def get_dominant_sentiment(sentiment_scores):
        if not isinstance(sentiment_scores, dict):
            return 'neutral'
        pos = sentiment_scores.get('positive', 0)
        neg = sentiment_scores.get('negative', 0)
        neu = sentiment_scores.get('neutral', 0)
        max_score = max(pos, neg, neu)
        if max_score == pos:
            return 'positive'
        elif max_score == neg:
            return 'negative'
        else:
            return 'neutral'

    filtered_comments = comments
    if sentiment_filter == "ポジティブ優勢":
        filtered_comments = [c for c in comments if get_dominant_sentiment(c.get('sentiment')) == 'positive']
    elif sentiment_filter == "ネガティブ優勢":
        filtered_comments = [c for c in comments if get_dominant_sentiment(c.get('sentiment')) == 'negative']
    elif sentiment_filter == "ニュートラル優勢":
        filtered_comments = [c for c in comments if get_dominant_sentiment(c.get('sentiment')) == 'neutral']

    st.write(f"表示中: {len(filtered_comments)}件 / 全{len(comments)}件")

    # Display comments
    for comment in filtered_comments:
        sentiment_scores = comment.get('sentiment', {})
        if isinstance(sentiment_scores, dict):
            pos = sentiment_scores.get('positive', 0)
            neg = sentiment_scores.get('negative', 0)
            neu = sentiment_scores.get('neutral', 0)

            sentiment_text = f"P:{pos:.2f} N:{neg:.2f} Neu:{neu:.2f}"
        else:
            sentiment_text = "スコアなし"

        # コメントテキストの冒頭を抽出（最大50文字）
        comment_text = comment.get('text', '')
        preview_text = comment_text[:50] + '...' if len(comment_text) > 50 else comment_text

        with st.expander(
            f"[{sentiment_text}] {preview_text} | {comment.get('author', 'Unknown')} - 👍 {comment.get('like_count', 0)}"
        ):
            st.write(comment_text)
            
            # Display sentiment scores
            if isinstance(sentiment_scores, dict):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("ポジ", f"{pos:.4f}")
                with col2:
                    st.metric("ネガ", f"{neg:.4f}")
                with col3:
                    st.metric("ニュートラル", f"{neu:.4f}")
            
            st.caption(f"投稿日: {comment.get('published_at', 'N/A')}")


def main():
    """Main Streamlit app."""
    st.title("📊 YouTube Comment Analyzer")
    st.markdown("YouTubeの動画IDまたはURLを入力して、コメントの感情分析を行います。")

    # Input section
    st.markdown("---")

    user_input = st.text_input(
        "YouTube動画IDまたはURL",
        placeholder="例: dQw4w9WgXcQ または https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    # Get comment limit from environment variable
    comment_limit = get_comment_limit()
    st.info(f"コメント取得数: {comment_limit}件 (設定ファイルで変更可能)")

    # Extract video ID preview
    if user_input:
        video_id = extract_video_id(user_input)
        if video_id:
            st.success(f"動画ID: `{video_id}`")
        else:
            st.error("有効なYouTube動画IDまたはURLを入力してください")

    # Analyze button
    analyze_button = st.button("分析開始", type="primary", use_container_width=True)

    # Analysis
    if analyze_button:
        if not user_input:
            st.error("動画IDまたはURLを入力してください")
            return

        video_id = extract_video_id(user_input)
        if not video_id:
            st.error("有効なYouTube動画IDまたはURLを入力してください")
            return

        with st.spinner(f"動画 `{video_id}` を分析中..."):
            try:
                result = analyze_video(video_id, comment_limit)

                if result:
                    st.success("分析完了!")

                    # Display results
                    display_video_info(result['video'])
                    st.markdown("---")
                    display_sentiment_summary(result['summary'])
                    st.markdown("---")
                    display_comments(result['comments'])
                else:
                    st.error("動画の取得に失敗しました。動画IDを確認してください。")

            except QuotaExceededError:
                logger.error("YouTube APIクォータ超過")
                st.error("YouTube APIの利用上限に達しました。明日再試行してください。")
            except CommentsDisabledError:
                logger.warning("コメントが無効化されています")
                st.warning("この動画はコメントが無効化されています。")
            except VideoNotFoundError:
                logger.warning("動画が見つかりません")
                st.error("動画が見つかりません。URLを確認してください。")
            except AuthenticationError:
                logger.error("YouTube API認証エラー")
                st.error("YouTube APIの認証に失敗しました。APIキーを確認してください。")
            except Exception as e:
                logger.error(f"分析中にエラーが発生しました: {e}")
                st.error(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()
