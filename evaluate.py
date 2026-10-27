"""Run every prompt strategy on the custom query set and score quality + consistency.

python evaluate.py [--repeats 3] [--rpm 10] [--backend mock]   (mock = plumbing test only)
Responses are cached in results/cache.jsonl, so an interrupted run resumes where it stopped.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

import metrics as M
from llm import LLM
from prompts import LABELS, STRATEGIES, build, parse_label

ROOT = Path(__file__).parent
RES = ROOT / "results"
ap = argparse.ArgumentParser()
ap.add_argument("--repeats", type=int, default=3)
ap.add_argument("--rpm", type=int, default=10)
ap.add_argument("--temp", type=float, default=0.7)
ap.add_argument("--backend", default=None)
a = ap.parse_args()
llm = LLM(backend=a.backend, rpm=a.rpm)
data = json.load(open(ROOT / "data" / "queries.json"))
cache_f = RES / ("cache_mock.jsonl" if llm.backend == "mock" else "cache.jsonl")
cache = {}
if cache_f.exists():
    for line in cache_f.read_text().splitlines():
        r = json.loads(line); cache[r["k"]] = r["out"]


def call(system, prompt, rep):
    k = hashlib.md5(f"{llm.model}|{a.temp}|{rep}|{system}|{prompt}".encode()).hexdigest()
    if k not in cache:
        cache[k] = llm.generate(prompt, system, temperature=a.temp)
        with open(cache_f, "a") as f:
            f.write(json.dumps({"k": k, "out": cache[k]}) + "\n")
    return cache[k]


recs = []
total = sum(len(data[t]) * len(STRATEGIES[t]) * a.repeats for t in STRATEGIES)
done = 0
t0 = time.time()
for task, strategies in STRATEGIES.items():
    for strat in strategies:
        for it in data[task]:
            system, prompt = build(task, strat, it)
            for rep in range(a.repeats):
                out = call(system, prompt, rep); done += 1
                r = {"task": task, "strategy": strat, "id": it["id"], "rep": rep, "output": out, "words": len(out.split())}
                if task == "qa":
                    r["abstain_expected"] = it["abstain"]; r["abstained"] = M.abstains(out)
                    if not it["abstain"]:
                        r["f1"] = M.f1(out, it["reference"]); r["rougeL"] = M.rouge_l(out, it["reference"])
                elif task == "summarize":
                    r["rouge1"] = M.rouge_1(out, it["reference"]); r["rougeL"] = M.rouge_l(out, it["reference"])
                    r["within_25"] = len(out.split()) <= 25
                    r["compression"] = len(out.split()) / len(it["text"].split())
                else:
                    r["pred"] = parse_label(task, out); r["gold"] = it["label"]; r["correct"] = r["pred"] == it["label"]
                recs.append(r)
        print(f"{task}/{strat} done ({done}/{total}, {time.time() - t0:.0f}s)", flush=True)

df = pd.DataFrame(recs)
rows = []
for (task, strat), g in df.groupby(["task", "strategy"]):
    row = {"task": task, "strategy": strat, "avg_words": g.words.mean()}
    if task == "qa":
        ex = g.abstain_expected.astype(bool)
        ans, un = g[~ex], g[ex]
        row.update(f1=ans.f1.mean(), rougeL=ans.rougeL.mean(), abstain_acc=un.abstained.mean(),
                   wrong_abstain=ans.abstained.mean())
        row["consistency"] = np.mean([M.text_consistency(x.output.tolist()) for _, x in g.groupby("id")])
        row["quality"] = row["f1"]
    elif task == "summarize":
        row.update(rouge1=g.rouge1.mean(), rougeL=g.rougeL.mean(), within_25=g.within_25.mean(), compression=g.compression.mean())
        row["consistency"] = np.mean([M.text_consistency(x.output.tolist()) for _, x in g.groupby("id")])
        row["quality"] = row["rougeL"]
    else:
        row.update(accuracy=g.correct.mean(), macro_f1=f1_score(g.gold, g.pred, labels=LABELS[task], average="macro", zero_division=0),
                   invalid_rate=(g.pred == "invalid").mean())
        row["consistency"] = np.mean([M.label_consistency(x.pred.tolist()) for _, x in g.groupby("id")])
        row["quality"] = row["accuracy"]
    rows.append(row)
summ = pd.DataFrame(rows)
tag = "_mock" if llm.backend == "mock" else ""
summ.to_csv(RES / f"summary{tag}.csv", index=False)
df.to_csv(RES / f"all_outputs{tag}.csv", index=False)
json.dump({"backend": llm.backend, "model": llm.model, "repeats": a.repeats, "temperature": a.temp,
           "summary": summ.to_dict("records")}, open(RES / f"results{tag}.json", "w"), indent=1)

fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for ax, col, title in zip(axes, ["quality", "consistency"], ["Quality (QA: F1 · Summ: ROUGE-L · Cls: accuracy)", "Consistency across repeated runs"]):
    p = summ.pivot(index="task", columns="strategy", values=col)
    p.plot.bar(ax=ax, rot=0); ax.set_ylim(0, 1); ax.set_title(title, fontsize=10); ax.set_xlabel("")
plt.tight_layout(); plt.savefig(RES / f"strategy_comparison{tag}.png", dpi=160)
print(summ.round(3).to_string())
