import re
from collections import Counter
from itertools import combinations


def toks(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def f1(pred, ref):
    p, r = Counter(toks(pred)), Counter(toks(ref))
    ov = sum((p & r).values())
    if not ov:
        return 0.0
    pr, rc = ov / sum(p.values()), ov / sum(r.values())
    return 2 * pr * rc / (pr + rc)


def _lcs(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            dp[i + 1][j + 1] = dp[i][j] + 1 if x == y else max(dp[i][j + 1], dp[i + 1][j])
    return dp[-1][-1]


def rouge_l(pred, ref):
    a, b = toks(pred), toks(ref)
    if not a or not b:
        return 0.0
    l = _lcs(a, b)
    if not l:
        return 0.0
    p, r = l / len(a), l / len(b)
    return 2 * p * r / (p + r)


def rouge_1(pred, ref):
    return f1(pred, ref)


ABSTAIN = re.compile(r"don't know|do not know|not available|no information|cannot|can't|unable|not aware|hasn't|has not|haven't|have not|not (yet )?(happened|released|exist)|false premise|premise|incorrect|not sure|no record|unknown", re.I)


def abstains(text):
    return bool(ABSTAIN.search(text))


def text_consistency(outs):
    """Mean pairwise ROUGE-L between repeated generations (1.0 = identical)."""
    pairs = list(combinations(outs, 2))
    return sum(rouge_l(a, b) for a, b in pairs) / len(pairs) if pairs else 1.0


def label_consistency(labels):
    """Share of runs agreeing with the most common label."""
    return Counter(labels).most_common(1)[0][1] / len(labels)
