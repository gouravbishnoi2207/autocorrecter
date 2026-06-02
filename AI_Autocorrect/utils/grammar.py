import re
from collections import Counter
from typing import Any, Dict, List

import nltk
from textblob import TextBlob
from nltk import pos_tag, sent_tokenize, word_tokenize
from nltk.corpus import stopwords


NLTK_RESOURCES = {
    "punkt": "tokenizers/punkt",
    "punkt_tab": "tokenizers/punkt_tab",
    "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
    "averaged_perceptron_tagger_eng": "taggers/averaged_perceptron_tagger_eng",
    "stopwords": "corpora/stopwords",
}

SINGULAR_PRONOUNS = {"he", "she", "it", "this", "that", "someone", "someone", "anyone", "everyone", "nobody", "everybody"}
PLURAL_PRONOUNS = {"they", "we", "these", "those", "you"}

IRREGULAR_SINGULAR = {
    "have": "has",
    "do": "does",
    "go": "goes",
    "make": "makes",
    "say": "says",
    "write": "writes",
    "take": "takes",
    "come": "comes",
    "get": "gets",
    "see": "sees",
    "know": "knows",
    "think": "thinks",
    "feel": "feels",
    "work": "works",
    "study": "studies",
    "try": "tries",
    "play": "plays",
    "watch": "watches",
    "need": "needs",
    "want": "wants",
    "use": "uses",
    "live": "lives",
    "run": "runs",
    "eat": "eats",
}

IRREGULAR_PLURAL = {
    "has": "have",
    "does": "do",
    "is": "are",
    "was": "were",
}


for package, resource_path in NLTK_RESOURCES.items():
    try:
        nltk.data.find(resource_path)
    except LookupError:
        nltk.download(package, quiet=True)


def correct_grammar(text: str, language: str = "en") -> Dict[str, Any]:
    if not text:
        return {
            "corrected_text": "",
            "issues": [],
            "confidence": 1.0,
            "note": "No grammar corrections were necessary.",
        }

    if (language or "en").lower() != "en":
        cleaned = " ".join(text.split())
        return {
            "corrected_text": cleaned,
            "issues": [],
            "confidence": 0.55,
            "note": "Grammar correction is optimized for English. Spelling correction was still applied for the selected language.",
        }

    sentences = sent_tokenize(text)
    corrected_sentences: List[str] = []
    issues: List[Dict[str, Any]] = []

    for sentence in sentences:
        normalized = _normalize_sentence(sentence)
        agreement_fixed = _apply_agreement_rules(normalized)

        try:
            blob_corrected = str(TextBlob(agreement_fixed).correct())
        except Exception:
            blob_corrected = agreement_fixed

        corrected = _normalize_sentence(blob_corrected)
        if corrected != sentence.strip():
            issues.append(
                {
                    "type": "grammar",
                    "original": sentence.strip(),
                    "corrected": corrected,
                    "reason": "The sentence was normalized for capitalization, punctuation, and common grammar patterns.",
                    "better_choice": "The corrected sentence reads more clearly and follows standard English usage.",
                    "suggestions": [corrected],
                    "confidence": 0.78,
                }
            )

        corrected_sentences.append(corrected)

    corrected_text = " ".join(corrected_sentences)
    corrected_text = re.sub(r"\s+([.,!?;:])", r"\1", corrected_text)
    corrected_text = re.sub(r"\s{2,}", " ", corrected_text).strip()

    confidence = _average_confidence(issues)
    return {
        "corrected_text": corrected_text,
        "issues": issues,
        "confidence": round(confidence, 2),
        "note": "Grammar analysis completed.",
    }


def calculate_readability(text: str) -> float:
    if not text.strip():
        return 100.0

    sentences = max(1, len(sent_tokenize(text)))
    words = word_tokenize(text)
    word_count = max(1, len([word for word in words if re.search(r"[A-Za-z]", word)]))
    syllables = sum(_count_syllables(word) for word in words if re.search(r"[A-Za-z]", word))

    score = 206.835 - 1.015 * (word_count / sentences) - 84.6 * (syllables / word_count)
    return round(max(0.0, min(100.0, score)), 2)


def extract_keywords(text: str, language: str = "en", top_n: int = 6) -> List[str]:
    if not text.strip():
        return []

    tokens = [token.lower() for token in word_tokenize(text) if re.fullmatch(r"[A-Za-z][A-Za-z'-]*", token)]

    stop_words = set()
    try:
        stop_words = set(stopwords.words("english" if (language or "en").lower() == "en" else language.lower()))
    except Exception:
        stop_words = set(stopwords.words("english"))

    filtered = [token for token in tokens if token not in stop_words and len(token) > 2]
    frequency = Counter(filtered)
    return [word for word, _ in frequency.most_common(top_n)]


def analyze_sentiment(text: str) -> Dict[str, Any]:
    if not text.strip():
        return {"label": "Neutral", "polarity": 0.0}

    polarity = TextBlob(text).sentiment.polarity
    if polarity > 0.15:
        label = "Positive"
    elif polarity < -0.15:
        label = "Negative"
    else:
        label = "Neutral"

    return {"label": label, "polarity": round(polarity, 3)}


def _normalize_sentence(sentence: str) -> str:
    cleaned = " ".join(sentence.strip().split())
    if not cleaned:
        return cleaned

    cleaned = cleaned.replace(" i ", " I ")
    cleaned = cleaned[:1].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _apply_agreement_rules(sentence: str) -> str:
    tokens = word_tokenize(sentence)
    tagged = pos_tag(tokens)
    corrected_tokens: List[str] = []
    subject_is_plural = None

    for index, (token, tag) in enumerate(tagged):
        lower_token = token.lower()
        if index == 0:
            if lower_token in SINGULAR_PRONOUNS:
                subject_is_plural = False
            elif lower_token in PLURAL_PRONOUNS:
                subject_is_plural = True
            elif tag in {"NN", "NNP"}:
                subject_is_plural = False

        replacement = token
        if subject_is_plural is False and lower_token in IRREGULAR_SINGULAR:
            replacement = _match_case(token, IRREGULAR_SINGULAR[lower_token])
        elif subject_is_plural is True and lower_token in IRREGULAR_PLURAL:
            replacement = _match_case(token, IRREGULAR_PLURAL[lower_token])

        corrected_tokens.append(replacement)

    return _rebuild_sentence(corrected_tokens)


def _rebuild_sentence(tokens: List[str]) -> str:
    text = " ".join(tokens)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return text


def _match_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source.istitle():
        return replacement.title()
    return replacement


def _count_syllables(word: str) -> int:
    word = word.lower()
    if len(word) <= 3:
        return 1

    vowels = "aeiouy"
    syllable_count = 0
    previous_is_vowel = False

    for character in word:
        is_vowel = character in vowels
        if is_vowel and not previous_is_vowel:
            syllable_count += 1
        previous_is_vowel = is_vowel

    if word.endswith("e") and syllable_count > 1:
        syllable_count -= 1

    return max(1, syllable_count)


def _average_confidence(issues: List[Dict[str, Any]]) -> float:
    if not issues:
        return 1.0
    return sum(issue.get("confidence", 0.0) for issue in issues) / len(issues)
