"""Aggregation module for sentiment analysis results."""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def aggregate_video(video: dict, comments: list[dict]) -> dict:
    """
    Aggregate sentiment analysis results for a video.

    Args:
        video: Video information dict
        comments: List of comment dicts with 'sentiment' field (dict with scores)

    Returns:
        Aggregated summary dict with counts, ratios, and scores
    """
    video_id = video.get('video_id', '')
    logger.info(f'動画の集計処理中: {video_id}')

    total_comments = len(comments)
    
    if total_comments == 0:
        return {
            'video_id': video_id,
            'total_comments': 0,
            'positive_count': 0,
            'negative_count': 0,
            'other_count': 0,
            'positive_ratio': 0.0,
            'negative_ratio': 0.0,
            'positive_score': 0.0,
            'negative_score': 0.0,
            'neutral_score': 0.0,
            'analyzed_at': datetime.now().isoformat()
        }
    
    # Count comments by dominant sentiment
    positive_count = 0
    negative_count = 0
    other_count = 0
    
    # Also calculate average sentiment scores
    positive_sum = 0.0
    negative_sum = 0.0
    neutral_sum = 0.0
    
    for comment in comments:
        sentiment_scores = comment.get('sentiment', {})
        pos = sentiment_scores.get('positive', 0)
        neg = sentiment_scores.get('negative', 0)
        neu = sentiment_scores.get('neutral', 0)

        # Accumulate scores for averaging
        positive_sum += pos
        negative_sum += neg
        neutral_sum += neu

        # Determine dominant sentiment for counting
        # Tie-breaking rule: If scores are tied, classify as 'other' (neutral/ambiguous)
        # This prevents arbitrary prioritization when sentiment is unclear
        max_score = max(pos, neg, neu)
        scores_at_max = sum(1 for s in [pos, neg, neu] if s == max_score)

        if scores_at_max > 1:
            # Multiple scores tied at max -> classify as other (ambiguous)
            other_count += 1
        elif max_score == pos:
            positive_count += 1
        elif max_score == neg:
            negative_count += 1
        else:
            other_count += 1
    
    # Calculate ratios (for DB storage)
    positive_ratio = round(positive_count / total_comments, 4)
    negative_ratio = round(negative_count / total_comments, 4)
    
    # Calculate average scores (for display/compatibility)
    positive_score = round(positive_sum / total_comments, 4)
    negative_score = round(negative_sum / total_comments, 4)
    neutral_score = round(neutral_sum / total_comments, 4)

    summary = {
        'video_id': video_id,
        'total_comments': total_comments,
        # Counts and ratios (for MySQL)
        'positive_count': positive_count,
        'negative_count': negative_count,
        'other_count': other_count,
        'positive_ratio': positive_ratio,
        'negative_ratio': negative_ratio,
        # Average scores (for display/compatibility)
        'positive_score': positive_score,
        'negative_score': negative_score,
        'neutral_score': neutral_score,
        'analyzed_at': datetime.now().isoformat()
    }

    logger.info(
        f'動画 {video_id}: コメント{total_comments}件, '
        f'カウント(pos={positive_count}, neg={negative_count}, other={other_count}), '
        f'スコア(pos={positive_score:.4f}, neg={negative_score:.4f}, neu={neutral_score:.4f})'
    )

    return summary
