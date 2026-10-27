"""Prompt templates: every task has a plain baseline and engineered strategies."""
import json
import re
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

ROOT = Path(__file__).parent
LABELS = {"sentiment": ["positive", "negative", "neutral"],
          "genre": ["action", "comedy", "horror", "romance", "sci-fi", "drama", "animation", "thriller"]}
STRATEGIES = {"qa": ["zero_shot", "role_constraints", "rag"],
              "summarize": ["zero_shot", "constrained", "few_shot"],
              "sentiment": ["zero_shot", "few_shot", "cot_json"],
              "genre": ["zero_shot", "few_shot", "cot_json"]}
DEFAULT_STRATEGY = {"qa": "rag", "summarize": "few_shot", "sentiment": "few_shot", "genre": "few_shot"}
PERSONA = "You are CineBot, a careful movie-industry assistant."


@lru_cache(maxsize=1)
def _faq():
    faq = json.load(open(ROOT / "data" / "faq.json"))
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit([f["q"] + " " + f["a"] for f in faq])
    return faq, vec, vec.transform([f["q"] + " " + f["a"] for f in faq])


def retrieve(question, k=3):
    faq, vec, mat = _faq()
    sims = linear_kernel(vec.transform([question]), mat).ravel()
    return [faq[i] for i in sims.argsort()[::-1][:k] if sims[i] > 0]


SUM_EXAMPLES = [
    ("Marlin, an anxious clownfish, loses his son Nemo to a diver and sets off across the ocean to find him. Along the way he teams up with Dory, a forgetful blue tang, and meets sharks, turtles and jellyfish. Marlin gradually learns to trust his son and let him take risks.",
     "An overprotective clownfish crosses the ocean with a forgetful friend to rescue his kidnapped son."),
    ("Woody, a cowboy doll, is the favourite toy of a boy named Andy until a flashy space-ranger toy, Buzz, arrives. Jealousy leads them both to be lost outside the house, and they must work together to get back before Andy moves.",
     "A jealous cowboy doll and a space-ranger toy must cooperate to find their way home.")]
CLS_EXAMPLES = {
    "sentiment": [("The acting was superb and the ending made me cry happy tears.", "positive"),
                  ("A boring mess with no plot and terrible editing.", "negative"),
                  ("Some good scenes, some bad ones, overall just okay.", "neutral"),
                  ("Funny, charming and beautifully shot. Loved every minute.", "positive")],
    "genre": [("Two rival gangs fight with guns and fast cars through the streets of Mumbai.", "action"),
              ("A group of campers hears whispers in the woods and vanishes one by one.", "horror"),
              ("A young couple meets in Paris and falls in love over a rainy week.", "romance"),
              ("A talking panda trains to become a kung-fu hero in a colourful cartoon world.", "animation")]}
TASK_WORD = {"sentiment": "the sentiment of the movie review", "genre": "the primary genre of the movie plot"}


def build(task, strategy, item):
    """Return (system, prompt) for an item. item: question | text."""
    if task == "qa":
        q = item["question"] if isinstance(item, dict) else item
        if strategy == "zero_shot":
            return None, q
        rules = ("Rules:\n- Answer in at most two sentences.\n- Use only facts you are certain about.\n"
                 "- If you are not sure, the event has not happened, or the question has a false premise, say \"I don't know\" and briefly say why.\n"
                 "- Never invent names, dates or numbers.")
        if strategy == "role_constraints":
            return PERSONA, f"{rules}\n\nQuestion: {q}\nAnswer:"
        ctx = "\n".join(f"- Q: {f['q']} A: {f['a']}" for f in retrieve(q))
        return PERSONA, (f"{rules}\n- Prefer the reference notes below when they are relevant.\n\n"
                         f"Reference notes:\n{ctx or '(none found)'}\n\nQuestion: {q}\nAnswer:")
    text = item["text"] if isinstance(item, dict) else item
    if task == "summarize":
        if strategy == "zero_shot":
            return None, f"Summarize this movie synopsis:\n\n{text}"
        rules = "Write exactly one sentence of at most 25 words. Name the main character or group and the central conflict. No spoilers about the ending unless essential. Output only the sentence."
        if strategy == "constrained":
            return PERSONA, f"{rules}\n\nSynopsis: {text}\nSummary:"
        ex = "\n\n".join(f"Synopsis: {s}\nSummary: {r}" for s, r in SUM_EXAMPLES)
        return PERSONA, f"{rules}\n\nExamples:\n\n{ex}\n\nNow summarize:\nSynopsis: {text}\nSummary:"
    labels = LABELS[task]
    lab = ", ".join(labels)
    if strategy == "zero_shot":
        return None, f"What is {TASK_WORD[task]} below?\n\n{text}"
    if strategy == "few_shot":
        ex = "\n".join(f"Text: {t}\nLabel: {l}" for t, l in CLS_EXAMPLES[task])
        return PERSONA, (f"Classify {TASK_WORD[task]} as exactly one of: {lab}.\nAnswer with the label only, in lowercase.\n\n{ex}\n\nText: {text}\nLabel:")
    return PERSONA, (f"Classify {TASK_WORD[task]} as exactly one of: {lab}.\nFirst reason briefly about the key evidence, then decide.\n"
                     f'Reply with only JSON: {{"reasoning": "<one or two sentences>", "label": "<one of {lab}>"}}\n\nText: {text}')


def parse_label(task, out):
    labels = LABELS[task]
    m = re.search(r'"label"\s*:\s*"([^"]+)"', out)
    s = (m.group(1) if m else out).lower().replace("science fiction", "sci-fi").replace("sci fi", "sci-fi")
    hits = [(s.find(l), l) for l in labels if l in s]
    return min(hits)[1] if hits else "invalid"
