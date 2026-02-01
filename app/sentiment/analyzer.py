"""Sentiment analysis module using language detection and multi-model inference."""

import logging
import os
import re
import threading

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from langdetect import detect, LangDetectException, DetectorFactory

logger = logging.getLogger(__name__)

# Ensure deterministic language detection
DetectorFactory.seed = 0

# Lock for thread-safe model loading
_model_lock = threading.Lock()

# Check for GPU availability
_device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
if _device.type == 'cpu':
    torch.set_num_threads(1)  # Single thread for CPU inference

# Japanese model 1: christian-phu (3-class: neg/neu/pos)
_ja_model_1 = None
_ja_tokenizer_1 = None
_ja_id2label_1 = None

# Japanese model 2: kit-nlp (2-class: pos/neg, irony detection)
_ja_model_2 = None
_ja_tokenizer_2 = None
_ja_id2label_2 = None

# Multilingual model (XLM-RoBERTa)
_multi_model = None
_multi_tokenizer = None
_multi_id2label = None

# Model names (configurable via environment variables)
JA_MODEL_1 = os.environ.get('JA_MODEL_1', 'christian-phu/bert-finetuned-japanese-sentiment')  # 3-class
JA_MODEL_2 = os.environ.get('JA_MODEL_2', 'kit-nlp/bert-base-japanese-sentiment-irony')  # 2-class, irony
MULTILINGUAL_MODEL = os.environ.get('MULTILINGUAL_MODEL', 'cardiffnlp/twitter-xlm-roberta-base-sentiment')

# Maximum token length for inference (with validation)
try:
    MAX_LENGTH = int(os.environ.get('MAX_TOKEN_LENGTH', '128'))
    if MAX_LENGTH < 1 or MAX_LENGTH > 512:
        logger.warning(f'MAX_TOKEN_LENGTHが範囲外です ({MAX_LENGTH})。デフォルト値128を使用します。')
        MAX_LENGTH = 128
except (ValueError, TypeError):
    logger.warning('MAX_TOKEN_LENGTH設定が無効です。デフォルト値128を使用します。')
    MAX_LENGTH = 128

# Fallback mode: use rules only when all models fail
FALLBACK_TO_RULES_ONLY = os.environ.get('FALLBACK_TO_RULES_ONLY', 'false').lower() == 'true'

# Rule-based dictionaries (module-level constants)
POSITIVE_WORDS = [
    # 日本語ポジティブ
    '最高', '素晴らしい', '良い', 'いい', 'よい', '好き', '大好き',
    '面白い', 'おもしろい', 'オモシロイ', '楽しい', 'たのしい',
    '感動', '感激', '泣いた', 'すごい', '凄い', 'ありがとう',
    '神', '完璧', '最強', '天才', 'センスある',
    'かわいい', '可愛い', 'きれい', '綺麗', 'かっこいい',
    '上手', 'うまい', '笑った', '爆笑', 'ウケる', '尊い', 'エモい',
    # 英語ポジティブ
    'good', 'great', 'nice', 'love', 'amazing', 'awesome', 'best',
    'excellent', 'perfect', 'fantastic', 'wonderful', 'beautiful',
    'cool', 'brilliant', 'impressive', 'incredible',
    # 絵文字
    '👍', '😊', '😄', '❤', '🎉', '👏', '💯', '😍', '🥰',
    '✨', '⭐', '🌟', '🔥', '😎', '🤩', '💕', '💖'
]

NEGATIVE_WORDS = [
    # 日本語ネガティブ
    'つまらない', 'つまんない', 'つまらん', 'ひどい', '酷い',
    '悪い', 'わるい', '嫌い', 'きらい', '最悪', '最低',
    'ダメ', 'だめ', '駄目', '残念', 'がっかり', '退屈',
    'うざい', 'ウザい', 'クソ', 'くそ', '糞', 'ゴミ', 'ごみ',
    'キモい', 'きもい', '不快', '胸糞', 'むかつく', 'イライラ',
    '無理', 'ありえない', '意味不明', '寒い', 'イタい', 'オワコン',
    '下手', 'ヘタ', 'パクリ', '嘘', 'やらせ', 'ステマ',
    '時間の無駄', '登録解除', '低評価', '詐欺', '炎上',
    # 英語ネガティブ
    'bad', 'worst', 'hate', 'boring', 'terrible', 'awful',
    'horrible', 'disgusting', 'trash', 'garbage', 'cringe',
    'stupid', 'dumb', 'sucks', 'annoying', 'pathetic',
    # 絵文字
    '👎', '😢', '😡', '💢', '😤', '🤮', '😒', '💩', '🤬',
    '😠', '😾', '🙄', '😑'
]

# Advanced rule patterns for sentiment adjustment (module-level constants for performance)
STRONG_NEGATIVE_PATTERNS = [
    # 基本的なネガティブ表現
    'つまらない', 'つまんない', 'つまらん', 'マジでつまらん', 'マジつまらん',
    'クッソつまらん', 'くっそつまらん', 'つまんね', 'つまんなすぎ',
    'ひどい', '酷い', 'ヒドイ', 'ひど過ぎ', '酷すぎ',
    '最悪', 'サイアク', '最低', 'サイテー', '史上最悪', '過去最悪',
    'クソ', 'くそ', '糞', 'クッソ', 'くっそ', 'クソすぎ', 'クソ過ぎ',
    'ゴミ', 'ごみ', 'ゴミすぎ', 'ゴミ動画', 'ゴミ企画', 'ゴミ編集',
    'うざい', 'ウザい', 'うぜえ', 'ウゼエ', 'ウザすぎ', 'うざすぎ', 'ウゼー',
    'キモい', 'きもい', 'キモすぎ', 'キショい', 'きしょい', '気持ち悪い', 'キモ',
    '嫌い', 'きらい', 'キライ', '大嫌い', 'だいきらい', '嫌いすぎ',
    '不快', '不愉快', '胸糞', '胸クソ', 'むかつく', 'ムカつく', 'イライラ',
    # YouTube特有の表現
    '時間の無駄', '時間返せ', '○分返せ', '時間返して', '人生の無駄',
    '見なきゃよかった', '見るんじゃなかった', '後悔', '見て損した',
    '登録解除', 'チャンネル登録解除', '登録解除しました', 'アンチ登録',
    '低評価', '低評価押した', '通報', '通報しました', 'BAD', 'bad押した',
    'がっかり', 'ガッカリ', '期待外れ', '期待はずれ', '期待裏切られた',
    '詐欺', 'サムネ詐欺', 'タイトル詐欺', '釣り', '釣りタイトル', '釣りサムネ',
    'やめて', 'やめろ', 'やめちまえ', '帰れ', '消えろ', '引退しろ', '辞めろ',
    '炎上', '問題', '炎上案件', 'アウト', 'やばい', 'ヤバい', 'ヤバイ', 'やばすぎ',
    'オワコン', 'オワコン化', '終わった', '終わってる', '劣化', '劣化した',
    # 感情表現
    '腹立つ', 'イラつく', 'ムカつく', 'うんざり', 'ウンザリ', 'しんどい',
    '無理', 'ムリ', 'ありえない', 'あり得ない', '意味不明', '理解不能',
    '寒い', 'さむい', 'サムい', '痛い', 'イタい', '恥ずかしい', '恥ずい',
    '見るに堪えない', '見てられない', '聞いてられない', '耐えられない',
    # 批判表現
    'ダメ', 'だめ', '駄目', 'ダメダメ', 'だめだめ', 'ダメすぎ',
    '下手', 'ヘタ', 'へた', '下手くそ', 'へたくそ', '下手すぎ',
    '雑', '適当', 'テキトー', 'いい加減', 'ずさん',
    'パクリ', 'ぱくり', 'パクった', 'コピー', '二番煎じ', '劣化コピー',
    '嘘', 'うそ', 'ウソ', '嘘つき', 'デマ', 'やらせ', 'ヤラセ', 'ステマ',
    # 攻撃的表現
    '死ね', 'くたばれ', '殺す', '殺したい', '〇ね', 'しね', 'タヒね',
    'アホ', 'あほ', 'バカ', 'ばか', 'ガイジ', 'カス', 'かす', 'クズ', 'くず',
    '障害', 'しょうがい', 'ゲェジ', 'ゴミクズ',
    # 曖昧・微妙なネガティブ
    '微妙', 'びみょう', 'ビミョー', '微妙すぎ',
    'なんか違う', 'コレジャナイ', 'これじゃない',
    # 皮肉・冷笑
    '草生える', '草も生えない', '草枯れる',
    'は？', 'はぁ？', 'え？', 'えぇ...', 'うーん',
    'なにこれ', '何これ', 'なんだこれ',
    # YouTube批判
    '見る価値なし', '時間泥棒', '金返せ',
    '案件', '案件臭', 'PR臭', '宣伝臭',
    '再生数稼ぎ', '金儲け', '収益化',
    # 飽き・マンネリ
    '飽きた', 'あきた', '飽きてきた',
    '冷めた', 'さめた', '冷める',
    '滑ってる', 'スベってる', 'すべってる', '滑り散らかし',
    'ワンパターン', 'マンネリ', 'いつもと同じ',
    '手抜き', '手ぬき', 'やっつけ',
    'やる気ない', 'やる気なさすぎ', 'やる気感じない',
    # 英語表現
    'bad', 'worst', 'terrible', 'awful', 'horrible', 'disgusting', 'hate',
    'waste of time', 'garbage', 'trash', 'cringe', 'cringey', 'creepy',
    'boring', 'stupid', 'dumb', 'sucks', 'shit', 'bullshit',
    'pathetic', 'lame', 'annoying', 'irritating', 'disappointing',
    'dislike', 'unsubscribed', 'clickbait', 'fake', 'scam',
    'meh', 'mediocre', 'overrated', 'overhyped',
    # 絵文字
    '👎', '😡', '💢', '😤', '🤮', '😒', '💩', '🤬', '😠', '😾',
    '🙄', '😑', '😐', '😓', '😰', '😨', '😱', '🤯', '😩', '😫'
]

SARCASM_PATTERNS = [
    # 棒読み・皮肉マーカー
    r'さすが.*[（(]棒[)）]', r'すごい.*[（(]棒[)）]', r'素晴らしい.*[（(]棒[)）]',
    r'[（(]棒[)）]', r'[（(]棒読み[)）]', r'[（(]白目[)）]',
    r'[（(]失笑[)）]', r'[（(]苦笑[)）]', r'[（(]呆れ[)）]', r'[（(]あきれ[)）]',
    r'[（(]笑[)）](?!.*www)', r'[（(]爆笑[)）](?!.*www)',
    r'[（(]真顔[)）]', r'[（(]遠い目[)）]', r'[（(]目が死んでる[)）]',
    # 婉曲表現
    'さすがですね', 'すごいですね', 'いいですね', '素晴らしいですね',
    'そうですね', 'そうなんだ', 'へえー', 'ふーん', 'へー', 'ほー',
    'なるほど', 'なるほどね', 'そっかー', 'そうかー',
    '分かりました', 'わかりました', '理解しました',
    # 過剰な褒め言葉（皮肉として機能）
    r'最高ですね[!！]{2,}', r'神[!！]{3,}', r'完璧[!！]{3,}',
    r'さすが[!！]{2,}', r'すばらしい[!！]{3,}',
    # 明確な皮肉表現
    'さすがだわ', 'お見事', '流石だわ', '参りました', '降参',
    'やりますね', 'やるなあ', '相変わらず', 'いつも通り',
    '予想通り', '想定内', '期待を裏切らない'
]

RHETORICAL_PATTERNS = [
    # 「これが〜？」型
    r'これが.*[?？]', r'この.*が.*[?？]', r'こんなの.*[?？]',
    # 「何が〜？」型
    r'何が.*[?？]', r'どこが.*[?？]', r'誰が.*[?？]', r'いつ.*[?？]',
    # 「どうして〜？」型
    r'どうして.*[?？]', r'なぜ.*[?？]', r'なんで.*[?？]',
    # 具体的な反語
    'これが面白いの', 'これが面白い？', 'これが面白いの？', 'これ面白い？',
    'これがいいの', 'これがいいの？', 'これが良いの？', 'これ良い？',
    '何が良いの', '何がいいの', '何が面白いの', '何がおもしろいの',
    'どこが面白い', 'どこがいい', 'どこが良い', 'どこがすごい',
    'どこが神', '何が神', 'これが神', 'どこが最高', '何が最高',
    'どこがかわいい', '何がかわいい', 'どこがいいの',
    '誰が見るの', '誰得', '需要ある？', '需要あるの？',
    'マジで言ってる？', 'まじで言ってる？', '本気で言ってる？',
    '正気か？', '正気？', '冗談だよね？', 'ネタだよね？',
    # 英語の反語
    'really?', 'seriously?', 'are you serious?', 'is this good?',
    'you serious?', 'for real?', 'are you kidding?',
    'what is this?', 'what the hell?', 'why?'
]

STRONG_POSITIVE_PATTERNS = [
    # 最上級の褒め言葉
    '最高', 'サイコー', '最高すぎ', '最高過ぎ', '史上最高', '過去最高',
    '神', '神回', '神動画', '神編集', '神企画', '神すぎ', '神ってる',
    '完璧', 'パーフェクト', '完璧すぎ', '完ぺき',
    '素晴らしい', 'すばらしい', '素晴らしすぎ', '素敵', 'ステキ', 'すてき',
    '最強', 'サイキョー', '最強すぎ', '無敵', 'ムテキ',
    # 感情表現
    '感動', '感動した', '感動的', '泣いた', '泣ける', '涙が出た', '涙出た',
    '感激', 'じーん', 'ジーン', 'グッときた', 'ぐっときた',
    '笑った', '爆笑', 'ワロタ', 'わろた', 'ウケる', 'うける', '面白すぎ',
    '楽しい', 'たのしい', 'タノシイ', '楽しすぎ', '楽しかった', '楽しめた',
    'すごい', '凄い', 'スゴい', 'すごすぎ', '凄すぎ', 'スゴすぎ', 'やばい',
    # 好意表現
    '好き', 'すき', 'スキ', '大好き', 'だいすき', 'ダイスキ', '好きすぎ',
    '愛してる', '大好物', '推せる', '推せます', '神推し',
    'ありがとう', 'ありがとうございます', 'サンキュー', 'thx', 'thanks',
    '尊い', 'とうとい', 'たまらん', 'たまらない', 'エモい', 'えもい',
    # 品質評価
    '面白い', 'おもしろい', 'オモシロイ', '面白すぎ', '超面白い', 'めっちゃ面白い',
    'かわいい', '可愛い', 'カワイイ', '可愛すぎ', 'かわいすぎ', 'かわゆい',
    'きれい', '綺麗', 'キレイ', '美しい', 'うつくしい', '美人', '可憐',
    'かっこいい', 'カッコいい', 'イケメン', 'かっこよすぎ',
    'いい', '良い', 'よい', 'いいね', '良いね', '良すぎ', 'めっちゃいい',
    'すごくいい', '超いい', 'めちゃいい', 'めちゃくちゃいい', 'メチャいい',
    # 強調表現
    '神回', '神コンテンツ', '名作', '傑作', '力作', '秀作', '良作',
    '天才', '天才的', 'すばらしすぎる', 'やばすぎる',
    '最高峰', 'トップレベル', 'ハイレベル', 'クオリティ高い',
    # 賞賛表現
    '上手', 'うまい', 'ウマい', '上手い', '上手すぎ', 'うますぎ',
    '天才', 'てんさい', 'センスある', 'センスいい', 'センス抜群',
    'プロ', 'プロ級', 'プロレベル', 'プロフェッショナル',
    '職人', '職人技', '匠', '技術がすごい', '技術力高い',
    # 応援表現
    '応援', '応援してる', '頑張れ', 'がんばれ', 'ファイト', 'ガンバ',
    '期待', '期待してる', '楽しみ', '楽しみにしてる', '待ってた', 'ずっと待ってた',
    '待ってました', 'まってました', '待望',
    'もっと見たい', 'また見たい', 'リピート', 'リピしてる', '何度も見た',
    '毎日見てる', '毎回見てる', 'ヘビロテ',
    '登録した', 'チャンネル登録した', '高評価', '高評価した', 'いいね押した',
    'グッドボタン', 'グッド', 'GOOD', 'good',
    # 共感・理解
    '共感', 'わかる', 'わかりみ', 'わかりみが深い',
    'それな', 'ほんとそれ', 'これ', 'これな', 'まさにこれ',
    '同意', '激しく同意', '禿同',
    # 癒し・元気
    '癒される', '癒し', '癒された', 'ほっこり',
    '元気出た', '元気もらった', '元気になった', '励まされた',
    '勇気もらった', 'パワーもらった',
    # 学び
    '勉強になる', '参考になる', 'ためになる', '助かる', '助かった',
    # 中毒性
    '中毒', '中毒性', '中毒になる', 'ハマる', 'はまる', 'ハマった',
    '沼', '沼落ち', '抜け出せない',
    # ポジティブな感嘆
    'やった', 'よし', 'いいぞ', 'ナイス', 'グッド', 'グレート',
    'わーい', 'やったー', 'よっしゃ', 'きたー', 'キター', 'キタ━',
    # 英語表現
    'amazing', 'awesome', 'excellent', 'perfect', 'fantastic', 'wonderful',
    'great', 'good', 'nice', 'beautiful', 'gorgeous', 'stunning',
    'love', 'loved', 'loved it', 'brilliant', 'magnificent', 'outstanding',
    'impressive', 'incredible', 'unbelievable', 'mindblowing', 'epic',
    'cool', 'dope', 'fire', 'lit', 'best', 'masterpiece',
    # 絵文字
    '❤', '💕', '💖', '💗', '💓', '💝', '💘', '😍', '🥰', '😊',
    '😄', '😁', '🤣', '😂', '🎉', '🎊', '👏', '👍', '💯', '✨',
    '⭐', '🌟', '💫', '🔥', '😎', '🤩', '😃', '😆', '🙌', '👌'
]

NEGATION_PATTERNS = [
    # 日本語否定
    'ない', 'なかった', 'なくて', 'ないな', 'ないね', 'ないわ',
    'ません', 'ませんでした', 'ぬ', 'ん', 'ず', 'んだ',
    # 英語否定
    'not', 'no', 'never', 'nothing', "don't", "doesn't",
    "didn't", "won't", "can't", "couldn't", "shouldn't"
]


def load_models() -> None:
    """Load sentiment analysis models (called only once at startup, thread-safe)."""
    global _ja_model_1, _ja_tokenizer_1, _ja_id2label_1
    global _ja_model_2, _ja_tokenizer_2, _ja_id2label_2
    global _multi_model, _multi_tokenizer, _multi_id2label

    # Quick check without lock (double-checked locking pattern)
    if _ja_model_1 is not None and _ja_model_2 is not None and _multi_model is not None:
        return  # Already loaded

    with _model_lock:
        # Check again inside lock to prevent race condition
        if _ja_model_1 is not None and _ja_model_2 is not None and _multi_model is not None:
            return  # Already loaded by another thread

        # Load Japanese model 1 (christian-phu: 3-class)
        try:
            logger.info(f'日本語モデル1をロード中: {JA_MODEL_1}')
            _ja_tokenizer_1 = AutoTokenizer.from_pretrained(JA_MODEL_1)
            _ja_model_1 = AutoModelForSequenceClassification.from_pretrained(JA_MODEL_1)
            _ja_model_1.to(_device)
            _ja_model_1.eval()
            _ja_id2label_1 = _ja_model_1.config.id2label if hasattr(_ja_model_1.config, 'id2label') else {0: 'negative', 1: 'neutral', 2: 'positive'}
            logger.info(f'日本語モデル1のロードに成功 (labels: {_ja_id2label_1})')
        except Exception as e:
            logger.error(f'日本語モデル1のロードに失敗: {e}')
            _ja_model_1 = None
            _ja_tokenizer_1 = None

        # Load Japanese model 2 (kit-nlp: 2-class, irony detection)
        try:
            logger.info(f'日本語モデル2をロード中: {JA_MODEL_2}')
            _ja_tokenizer_2 = AutoTokenizer.from_pretrained(JA_MODEL_2)
            _ja_model_2 = AutoModelForSequenceClassification.from_pretrained(JA_MODEL_2)
            _ja_model_2.to(_device)
            _ja_model_2.eval()
            _ja_id2label_2 = _ja_model_2.config.id2label if hasattr(_ja_model_2.config, 'id2label') else {0: 'ポジティブ', 1: 'ネガティブ'}
            logger.info(f'日本語モデル2のロードに成功 (labels: {_ja_id2label_2})')
        except Exception as e:
            logger.error(f'日本語モデル2のロードに失敗: {e}')
            _ja_model_2 = None
            _ja_tokenizer_2 = None

        # Load multilingual model
        try:
            logger.info(f'多言語モデルをロード中: {MULTILINGUAL_MODEL}')
            _multi_tokenizer = AutoTokenizer.from_pretrained(MULTILINGUAL_MODEL)
            _multi_model = AutoModelForSequenceClassification.from_pretrained(MULTILINGUAL_MODEL)
            _multi_model.to(_device)
            _multi_model.eval()
            _multi_id2label = _multi_model.config.id2label if hasattr(_multi_model.config, 'id2label') else {0: 'negative', 1: 'neutral', 2: 'positive'}
            logger.info(f'多言語モデルのロードに成功 (labels: {_multi_id2label})')
        except Exception as e:
            logger.error(f'多言語モデルのロードに失敗: {e}')
            _multi_model = None
            _multi_tokenizer = None


def _detect_language(text: str) -> str:
    """
    Detect language of text using character-based heuristics and langdetect.

    Args:
        text: Input text

    Returns:
        Language code ('ja' for Japanese, 'other' for others)
    """
    # Check for Japanese characters first (more reliable for short texts)
    # Hiragana: \u3040-\u309F, Katakana: \u30A0-\u30FF, Kanji: \u4E00-\u9FFF
    japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]')
    if japanese_pattern.search(text):
        return 'ja'

    # For texts without Japanese characters, use langdetect
    try:
        lang_code = detect(text)
        return 'ja' if lang_code == 'ja' else 'other'
    except LangDetectException as e:
        logger.warning(f'言語判定エラー: {e}')
        # Default to multilingual model for ambiguous cases
        return 'other'


def _preprocess_text(text: str) -> str:
    """Preprocess text for classification."""
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.strip()


def _rule_based_classify(text: str) -> str:
    """Simple rule-based sentiment classification (binary: pos/neg)."""

    text_lower = text.lower()

    pos_count = sum(1 for word in POSITIVE_WORDS if word in text_lower or word in text)
    neg_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower or word in text)

    # Binary classification: always return pos or neg
    if pos_count >= neg_count:
        return 'pos'
    else:
        return 'neg'


def _adjust_sentiment_with_rules(text: str, scores: dict) -> dict:
    """
    Apply advanced rule-based correction to sentiment scores.
    Detects YouTube-specific expressions including sarcasm, irony, and rhetorical questions.

    Args:
        text: Original text
        scores: Model prediction scores {"positive": float, "negative": float, "neutral": float}

    Returns:
        dict: Corrected scores with accumulated adjustments (max 0.4)
    """
    text_lower = text.lower()

    # パターンマッチング（モジュールレベル定数を使用）
    neg_match_count = sum(1 for pattern in STRONG_NEGATIVE_PATTERNS if pattern in text_lower or pattern in text)
    pos_match_count = sum(1 for pattern in STRONG_POSITIVE_PATTERNS if pattern in text_lower or pattern in text)

    # 正規表現パターンマッチング
    sarcasm_match = any(re.search(pattern, text) for pattern in SARCASM_PATTERNS)
    rhetorical_match = any(re.search(pattern, text) for pattern in RHETORICAL_PATTERNS)

    # 否定表現の検出
    has_negation = any(pattern in text_lower for pattern in NEGATION_PATTERNS)

    # スコア補正値の初期化
    positive_adjustment = 0.0
    negative_adjustment = 0.0
    neutral_adjustment = 0.0

    corrections_applied = []

    # 1. 強いネガティブ表現の補正
    if neg_match_count >= 2:
        negative_adjustment += 0.25
        positive_adjustment -= 0.25
        corrections_applied.append(f'強ネガ表現x{neg_match_count}')
    elif neg_match_count >= 1:
        negative_adjustment += 0.15
        positive_adjustment -= 0.15
        corrections_applied.append(f'ネガ表現x{neg_match_count}')

    # 2. 皮肉表現の補正
    if sarcasm_match:
        negative_adjustment += 0.2
        positive_adjustment -= 0.2
        corrections_applied.append('皮肉検出')

    # 3. 反語表現の補正
    if rhetorical_match:
        negative_adjustment += 0.2
        positive_adjustment -= 0.2
        corrections_applied.append('反語検出')

    # 4. ポジティブ+否定 = ネガティブ（例: 面白くない）
    if pos_match_count >= 1 and has_negation:
        negative_adjustment += 0.2
        positive_adjustment -= 0.2
        corrections_applied.append('ポジ+否定')
    # 5. ポジティブ表現の補正（否定がない場合のみ）
    elif pos_match_count >= 2 and not has_negation:
        positive_adjustment += 0.25
        negative_adjustment -= 0.25
        corrections_applied.append(f'強ポジ表現x{pos_match_count}')
    elif pos_match_count >= 1 and not has_negation:
        positive_adjustment += 0.15
        negative_adjustment -= 0.15
        corrections_applied.append(f'ポジ表現x{pos_match_count}')

    # 補正値を最大0.3に制限（3クラスモデル対応）
    negative_adjustment = max(min(negative_adjustment, 0.3), -0.3)
    positive_adjustment = max(min(positive_adjustment, 0.3), -0.3)

    # スコアに補正を適用
    corrected = scores.copy()
    corrected['negative'] = max(min(corrected['negative'] + negative_adjustment, 1.0), 0.0)
    corrected['positive'] = max(min(corrected['positive'] + positive_adjustment, 1.0), 0.0)
    corrected['neutral'] = max(corrected['neutral'] + neutral_adjustment, 0.0)

    # 正規化（合計を1.0に）
    total = corrected['positive'] + corrected['negative'] + corrected['neutral']
    if total > 0:
        corrected['positive'] /= total
        corrected['negative'] /= total
        corrected['neutral'] /= total

    # ログ出力（ルール補正は重要な情報なのでINFOレベル）
    if corrections_applied:
        logger.info(f'ルール補正適用: {", ".join(corrections_applied)} | '
                   f'調整値 pos:{positive_adjustment:+.2f} neg:{negative_adjustment:+.2f} | '
                   f'結果 P:{corrected["positive"]:.3f} N:{corrected["negative"]:.3f} Neu:{corrected["neutral"]:.3f}')

    return corrected


def _single_model_inference(text: str, model, tokenizer, id2label) -> dict:
    """
    Perform inference using a single model.
    Returns probability scores for pos, neg, neutral.
    """
    if model is None or tokenizer is None:
        return None

    try:
        inputs = tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors='pt'
        )
        inputs = {k: v.to(_device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=-1)[0]

        scores = probabilities.cpu().numpy()

        # Handle different model configurations
        if len(scores) == 3:
            if id2label and id2label.get(0) == 'negative':
                # Format: 0=negative, 1=neutral, 2=positive
                return {
                    "positive": float(scores[2]),
                    "negative": float(scores[0]),
                    "neutral": float(scores[1])
                }
            else:
                return {
                    "positive": float(scores[1]),
                    "negative": float(scores[0]),
                    "neutral": float(scores[2])
                }
        elif len(scores) == 2:
            # Binary model (kit-nlp: 0=ポジティブ, 1=ネガティブ)
            if id2label and (id2label.get(0) == 'ポジティブ' or id2label.get(0, '').lower() == 'positive'):
                return {
                    "positive": float(scores[0]),
                    "negative": float(scores[1]),
                    "neutral": 0.0
                }
            else:
                return {
                    "positive": float(scores[1]),
                    "negative": float(scores[0]),
                    "neutral": 0.0
                }
        else:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}
    except Exception as e:
        logger.warning(f'Model inference error: {e}')
        return None


def _pytorch_inference(text: str, language: str) -> dict:
    """
    Perform inference using PyTorch.
    For Japanese: ensemble of 2 models (christian-phu + kit-nlp)
    For other languages: XLM-RoBERTa

    Args:
        text: Preprocessed text
        language: Language code ('ja' or 'other')

    Returns:
        dict: {"positive": float, "negative": float, "neutral": float}
    """
    global _ja_model_1, _ja_tokenizer_1, _ja_id2label_1
    global _ja_model_2, _ja_tokenizer_2, _ja_id2label_2
    global _multi_model, _multi_tokenizer, _multi_id2label

    if language == 'ja':
        # Ensemble for Japanese: average of 2 models
        result_1 = _single_model_inference(text, _ja_model_1, _ja_tokenizer_1, _ja_id2label_1)
        result_2 = _single_model_inference(text, _ja_model_2, _ja_tokenizer_2, _ja_id2label_2)

        if result_1 is not None and result_2 is not None:
            # Average both models (kit-nlp has neutral=0, so it contributes less to neutral)
            return {
                "positive": (result_1["positive"] + result_2["positive"]) / 2,
                "negative": (result_1["negative"] + result_2["negative"]) / 2,
                "neutral": (result_1["neutral"] + result_2["neutral"]) / 2
            }
        elif result_1 is not None:
            return result_1
        elif result_2 is not None:
            return result_2
        else:
            # Fallback to rule-based
            label = _rule_based_classify(text)
            if label == 'pos':
                return {"positive": 0.6, "negative": 0.15, "neutral": 0.25}
            else:
                return {"positive": 0.15, "negative": 0.6, "neutral": 0.25}
    else:
        # Multilingual model for other languages
        result = _single_model_inference(text, _multi_model, _multi_tokenizer, _multi_id2label)
        if result is not None:
            return result
        else:
            label = _rule_based_classify(text)
            if label == 'pos':
                return {"positive": 0.6, "negative": 0.15, "neutral": 0.25}
            else:
                return {"positive": 0.15, "negative": 0.6, "neutral": 0.25}


def classify_comment(text: str) -> dict:
    """
    Classify sentiment for a single comment with language detection.
    For Japanese: uses ensemble of 2 models (christian-phu + kit-nlp)
    For other languages: uses XLM-RoBERTa
    Returns probability scores for positive, negative, and neutral.

    Args:
        text: Comment text

    Returns:
        dict: {"positive": float, "negative": float, "neutral": float, "language": str}
    """
    if not text or not text.strip():
        return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "language": "unknown"}

    processed_text = _preprocess_text(text)
    if not processed_text:
        return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "language": "unknown"}

    # Detect language
    language = _detect_language(processed_text)

    # Use PyTorch inference with appropriate model (ensemble for Japanese)
    result = _pytorch_inference(processed_text, language)

    result["language"] = language

    return result


def _classify_comment_rules_only(text: str) -> dict:
    """
    Classify sentiment using rules only (fallback mode).
    Returns scores in the same format as model-based classification.

    Args:
        text: Comment text

    Returns:
        dict: {"positive": float, "negative": float, "neutral": float, "language": str}
    """
    if not text or not text.strip():
        return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "language": "unknown"}

    processed_text = _preprocess_text(text)
    if not processed_text:
        return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "language": "unknown"}

    language = _detect_language(processed_text)
    label = _rule_based_classify(processed_text)

    # Convert rule-based label to scores
    if label == 'pos':
        base_scores = {"positive": 0.6, "negative": 0.15, "neutral": 0.25}
    else:
        base_scores = {"positive": 0.15, "negative": 0.6, "neutral": 0.25}

    # Apply rule adjustments for more nuanced scoring
    adjusted = _adjust_sentiment_with_rules(processed_text, base_scores)
    adjusted["language"] = language

    return adjusted


def classify_comments(comments: list[dict]) -> list[dict]:
    """
    Classify sentiment for a list of comments.

    Args:
        comments: List of comment dicts

    Returns:
        List of comment dicts with 'sentiment' field added

    Raises:
        RuntimeError: If all models failed to load and FALLBACK_TO_RULES_ONLY is False
    """
    # Load models once at the beginning
    load_models()

    # Check if at least one model loaded successfully
    all_models_failed = _ja_model_1 is None and _ja_model_2 is None and _multi_model is None

    if all_models_failed:
        if FALLBACK_TO_RULES_ONLY:
            logger.warning('全てのモデルのロードに失敗しました。ルールベースのみで感情分析を実行します。')
            for comment in comments:
                comment['sentiment'] = _classify_comment_rules_only(comment.get('text', ''))
            return comments
        else:
            error_msg = '全ての感情分析モデルのロードに失敗しました。環境変数とモデルファイルを確認してください。FALLBACK_TO_RULES_ONLY=true でルールベースフォールバックを有効化できます。'
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    # Process comments sequentially (no parallel processing)
    for comment in comments:
        comment['sentiment'] = classify_comment(comment.get('text', ''))

    return comments
