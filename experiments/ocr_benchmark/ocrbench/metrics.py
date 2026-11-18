"""Explicit denominators; NFC preserves clinically meaningful punctuation and case."""
import collections
import unicodedata

from rapidfuzz.distance import Levenshtein


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def distance_counts(reference, prediction):
    edits = Levenshtein.editops(reference, prediction)
    counts = collections.Counter(op.tag for op in edits)
    return {"substitutions": counts["replace"], "deletions": counts["delete"],
            "insertions": counts["insert"], "reference_length": len(reference),
            "prediction_length": len(prediction), "edit_distance": len(edits)}


def ratio(numerator, denominator):
    # Empty reference: errors exist but no reference denominator. Keep counts.
    return numerator / denominator if denominator else None


def text_metrics(reference, prediction):
    reference, prediction = normalize(reference), normalize(prediction)
    chars = distance_counts(reference, prediction)
    words = distance_counts(reference.split(), prediction.split())
    overlap = sum((collections.Counter(reference.split()) &
                   collections.Counter(prediction.split())).values())
    precision = ratio(overlap, words["prediction_length"])
    recall = ratio(overlap, words["reference_length"])
    return {
        "characters": chars, "words": words,
        "cer": ratio(chars["edit_distance"], chars["reference_length"]),
        "wer": ratio(words["edit_distance"], words["reference_length"]),
        "normalized_edit_distance": ratio(chars["edit_distance"],
                                         max(len(reference), len(prediction))),
        "token_precision": precision, "token_recall": recall,
        "token_f1": 2 * overlap / (len(reference.split()) + len(prediction.split()))
                    if reference or prediction else None,
        "token_omission_rate": ratio(words["deletions"], words["reference_length"]),
        "token_insertion_rate": ratio(words["insertions"], words["reference_length"]),
        "exact_match": reference == prediction,
    }


def field_metrics(reference, prediction):
    """Exact normalized key/value matching, wrong value counts FP and FN."""
    expected = {(key, normalize(str(value))) for key, value in reference.items()}
    actual = {(key, normalize(str(value))) for key, value in prediction.items()}
    tp, fp, fn = len(expected & actual), len(actual - expected), len(expected - actual)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn), "f1": ratio(2 * tp, 2 * tp + fp + fn)}


def teds(reference, prediction, structure_only=False):
    """PubTabNet-style HTML tree similarity: ordered APTED, cell edit cost.

    Input must be one HTML table per matched pair. Missing/malformed prediction=0.
    This is an independent implementation; validate against upstream before
    comparing published leaderboard numbers.
    """
    from apted import APTED, Config
    from lxml import etree, html

    class Node:
        def __init__(self, element):
            self.tag = element.tag
            self.span = (int(element.get("rowspan", "1")), int(element.get("colspan", "1"))) if element.tag == 'td' else None
            self.content = self.tokens(element) if element.tag == "td" else []
            self.children = [] if self.content or element.tag == "td" else [
                Node(child) for child in element if isinstance(child.tag, str)]

        @classmethod
        def tokens(cls, element):
            result = list(element.text or "")
            for child in element:
                if isinstance(child.tag, str):
                    result += ["<" + child.tag + ">"] + cls.tokens(child) + ["</" + child.tag + ">"]
                result += list(child.tail or "")
            return result

    def parse(value):
        root = html.fromstring(value, parser=html.HTMLParser(no_network=True, remove_comments=True))
        tables = [root] if root.tag == "table" else root.xpath(".//table")
        if len(tables) != 1:
            raise ValueError("Expected exactly one table")
        table = tables[0]
        return Node(table), max(1, len(table.xpath(".//*")))

    class Cost(Config):
        def rename(self, left, right):
            if left.tag != right.tag or left.span != right.span:
                return 1
            if not structure_only and left.tag == "td":
                return Levenshtein.distance(left.content, right.content) / max(
                    len(left.content), len(right.content), 1)
            return 0

    a, size_a = parse(reference)
    try:
        b, size_b = parse(prediction)
    except (ValueError, etree.ParserError):
        return 0.0
    return max(0.0, 1 - APTED(a, b, Cost()).compute_edit_distance() / max(size_a, size_b))
