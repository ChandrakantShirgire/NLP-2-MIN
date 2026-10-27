"""Builds CineBot_NLP_CA3_Report.docx in the NLP CA-3 format. Numbers come from results/results.json
(created by `python evaluate.py` with a real API key); until then those tables show yellow placeholders."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from prompts import STRATEGIES

ROOT = Path(__file__).parent
RES = ROOT / "results"
rf = RES / "results.json"
R = json.load(open(rf)) if rf.exists() else None
if R and R["backend"] == "mock":
    R = None
S = {(r["task"], r["strategy"]): r for r in R["summary"]} if R else {}
Q = json.load(open(ROOT / "data" / "queries.json"))
nfaq = len(json.load(open(ROOT / "data" / "faq.json")))

# ---------------------------------------------------------------- architecture figure
fig, ax = plt.subplots(figsize=(11, 3.6)); ax.axis("off")
cols = ["#eaf2fb", "#fdf2e3", "#eaf7ee"]
top = [("User message\n(Streamlit chat)", 0), ("Task router\n(Q&A · summarise ·\nsentiment · genre)", 1), ("Prompt builder\n(strategy templates)", 2),
       ("LLM API\n(Gemini)", 3), ("Post-processing\n(label parser,\nabstain check)", 4), ("Reply +\ntask/strategy tag", 5)]
for t, i in top:
    x = i * 1.8
    ax.add_patch(plt.Rectangle((x, 1.2), 1.5, .8, fc=cols[i % 3], ec="#1f4e79", lw=1.4)); ax.text(x + .75, 1.6, t, ha="center", va="center", fontsize=8.5)
    if i < 5:
        ax.annotate("", xy=(x + 1.78, 1.6), xytext=(x + 1.5, 1.6), arrowprops=dict(arrowstyle="->", color="#1f4e79", lw=1.5))
ax.add_patch(plt.Rectangle((3.6, 0.1), 1.5, .7, fc="#fff9c4", ec="#7f6000", lw=1.4)); ax.text(4.35, .45, f"FAQ knowledge base\n({nfaq} entries, TF-IDF retrieval)", ha="center", va="center", fontsize=8)
ax.annotate("", xy=(3.6, 1.2), xytext=(4.0, .8), arrowprops=dict(arrowstyle="->", color="#7f6000", lw=1.4)); ax.text(3.55, .95, "RAG context", fontsize=7.5, ha="right")
ax.add_patch(plt.Rectangle((7.2, 0.1), 3.6, .7, fc="#f3e5f5", ec="#4a148c", lw=1.4)); ax.text(9, .45, "Evaluation harness: quality metrics + repeated-run consistency", ha="center", va="center", fontsize=8)
ax.set_xlim(-.1, 10.9); ax.set_ylim(0, 2.2); plt.tight_layout(); plt.savefig(RES / "architecture.png", dpi=170); plt.close()

# ---------------------------------------------------------------- doc helpers
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Inches(1)
FONT = "Times New Roman"
for name, size, bold in [("Normal", 12, False), ("Heading 1", 14, True), ("Heading 2", 12, True), ("Title", 18, True)]:
    st = doc.styles[name]; st.font.name = FONT; st.font.size = Pt(size); st.font.bold = bold; st.font.color.rgb = None
    rpr = st.element.get_or_add_rPr(); f = rpr.find(qn("w:rFonts"))
    if f is None:
        f = OxmlElement("w:rFonts"); rpr.append(f)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        f.set(qn(a), FONT)
    st.paragraph_format.line_spacing = 1.15
doc.styles["Normal"].paragraph_format.space_after = Pt(6)
for n in ("Heading 1", "Heading 2"):
    doc.styles[n].paragraph_format.space_before = Pt(12); doc.styles[n].paragraph_format.keep_with_next = True


def P(text="", bold=False, italic=False, align=None, size=None):
    p = doc.add_paragraph()
    p.alignment = {"c": WD_ALIGN_PARAGRAPH.CENTER, "l": WD_ALIGN_PARAGRAPH.LEFT}.get(align, WD_ALIGN_PARAGRAPH.JUSTIFY)
    for i, seg in enumerate(text.split("[[")):
        if i == 0:
            r = p.add_run(seg)
        else:
            slot, rest = seg.split("]]", 1)
            h = p.add_run("[" + slot + "]"); h.font.highlight_color = WD_COLOR_INDEX.YELLOW
            r = p.add_run(rest)
        r.bold, r.italic = bold, italic
        if size: r.font.size = Pt(size)
    return p


def B(text, lead=None):
    p = doc.add_paragraph(style="List Bullet"); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if lead: p.add_run(lead).bold = True
    p.add_run(text)


def H1(t): doc.add_heading(t, 1)
def H2(t): doc.add_heading(t, 2)


def shade(c, color):
    pr = c._tc.get_or_add_tcPr(); s = OxmlElement("w:shd"); s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), color); pr.append(s)


tc, fc = [0], [0]


def table(caption, header, rows, widths=None):
    tc[0] += 1
    P(f"Table {tc[0]}: {caption}", bold=True, align="c", size=11)
    t = doc.add_table(rows=1, cols=len(header)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(10); shade(c, "D9E2F3")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            txt = str(v); hl = txt.startswith("[[")
            r = cells[i].paragraphs[0].add_run(txt.strip("[]") if hl else txt); r.font.size = Pt(10)
            if hl: r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    for row in t.rows:
        for i, c in enumerate(row.cells):
            for p in c.paragraphs: p.paragraph_format.line_spacing = 1.0; p.paragraph_format.space_after = Pt(2)
            if widths: c.width = Inches(widths[i])
    doc.add_paragraph()


def figure(path, caption, w=6.0):
    fc[0] += 1
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(w))
    P(f"Figure {fc[0]}: {caption}", bold=True, align="c", size=11)


def val(task, strat, key, fmt="{:.3f}"):
    r = S.get((task, strat))
    return fmt.format(r[key]) if r and r.get(key) == r.get(key) and r.get(key) is not None else "[[run evaluate.py]]"


# ---------------------------------------------------------------- title block
P("CA-3 Project Report", bold=True, align="c", size=14)
for line in ["Course: Natural Language Processing Lab (TEE7100)", "Department: Computer Science & Engineering", "Institute: Symbiosis Institute of Technology, Pune",
             "Academic Year: 2026–27", "Student Name: Vedant Nair", "PRN: 23070122230", "Group Number: [[group no.]]"]:
    P(line, align="l")
P("CineBot: A Movie-Domain Chatbot Using a Large Language Model with Prompt Engineering for Question Answering, Summarisation and Classification", bold=True, align="c", size=16)

# ---------------------------------------------------------------- abstract
H1("Abstract")
if R:
    best = {t: max(STRATEGIES[t], key=lambda s: S[(t, s)]["quality"]) for t in STRATEGIES}
    resline = "; ".join(f"for {t} the best strategy was {best[t]} ({S[(t, best[t])]['quality']:.2f} versus {S[(t, STRATEGIES[t][0])]['quality']:.2f} for the plain baseline)" for t in STRATEGIES)
    resline = f"On {sum(len(Q[t]) for t in Q)} custom queries evaluated over {R['repeats']} repeated runs, {resline}."
else:
    resline = "[[Key result sentence: run evaluate.py, then rebuild this report to fill it automatically.]]"
P("Large language models (LLMs) can answer questions, summarise text and classify it without task-specific training, but their output quality depends strongly on how the instruction is written. This project builds CineBot, a chatbot for the movie domain that handles three tasks with a single LLM API: question answering about films and the film industry, one-sentence summarisation of movie synopses, and classification of review sentiment and plot genre. For each task we design a plain zero-shot baseline and two engineered prompts that use role definition, explicit output constraints, few-shot examples, structured reasoning with JSON output, and retrieval-augmented grounding on a "
  f"{nfaq}-entry movie FAQ. The evaluation set comprises custom queries: {len(Q['qa'])} Q&A items (including four unanswerable or false-premise questions that test hallucination), {len(Q['summarize'])} synopses, {len(Q['sentiment'])} reviews and {len(Q['genre'])} plot blurbs. Responses are scored for quality (token F1 and ROUGE against references, accuracy and macro-F1, abstention accuracy) and for consistency (agreement or mean pairwise ROUGE-L across repeated generations at non-zero temperature). "
  + resline + " The system is delivered as a Streamlit chatbot in which the user can switch tasks and prompt strategies. Future work includes LLM-as-judge scoring, larger datasets and multilingual (Hindi) support.")
P("Keywords: large language model, prompt engineering, chatbot, retrieval-augmented generation, few-shot prompting, movie domain, consistency evaluation.", italic=True)

# ---------------------------------------------------------------- 1 intro
H1("1. Introduction")
P("Conversational assistants are now part of how people discover and discuss films. Viewers ask what a certificate means, which director made a film or what a plot is about; critics and platforms need quick summaries of long synopses and want to tag thousands of reviews by sentiment and genre. Streaming services, ticketing apps, film festivals and fan communities are the main stakeholders, and all of them need answers that are fast, short and, above all, correct.")
P("LLMs are attractive because one model can perform all of these tasks, but they are known to be sensitive to the wording of the prompt, to give different answers to the same question when sampling is enabled, and to hallucinate facts, for example by confidently naming a director for a film that does not exist. For a movie chatbot, an invented fact such as the wrong release year or award is a visible failure.")
P("The motivation of this work is to treat prompt design as an engineering discipline: instead of one hand-written prompt, we compare several prompt strategies per task under the same model and score them with measurable criteria. The research gap is that many chatbot projects only demonstrate a few chat examples; they do not measure response quality or the consistency of repeated answers, and they do not test how the bot behaves on unanswerable questions.")
P("The objectives are: (i) design prompts for question answering, summarisation and classification; (ii) generate responses with an LLM API; (iii) evaluate response quality and consistency; and (iv) improve performance using prompt-engineering techniques. The NLP techniques used are zero-shot, role, few-shot and structured prompting, TF-IDF retrieval for grounding, and n-gram overlap metrics. The datasets are a custom movie FAQ and a custom query set.")
P("Major contributions:")
B("A multi-task movie chatbot with a task router and strategy selector.")
B("A library of nine task–strategy prompt templates, including a retrieval-grounded Q&A prompt.")
B("A reproducible evaluation harness that measures quality and run-to-run consistency, including an abstention test for hallucination.")
B("A comparative analysis showing which prompt-engineering techniques help each task.")

# ---------------------------------------------------------------- 2 lit review
H1("2. Literature Review")
P("Prompting research began with showing that LLMs can follow instructions without gradient updates. Ouyang et al. (2022) aligned GPT-3 models to follow instructions with human feedback, which made direct natural-language instructions practical. Wei et al. (2022) showed that chain-of-thought prompts, which include intermediate reasoning steps, substantially improve performance on arithmetic and commonsense reasoning, and Kojima et al. (2022) found that even the zero-shot phrase “Let’s think step by step” elicits such reasoning. Wang et al. (2023) added self-consistency, sampling several reasoning paths and taking the majority answer, which directly motivates our use of repeated runs to measure and exploit consistency. Yao et al. (2023) combined reasoning with tool actions in ReAct.")
P("A second thread examines what makes demonstrations effective. Min et al. (2022) reported that the label space and format of few-shot examples matter more than whether the individual labels are correct, which supports our use of short, format-focused examples. Bsharat et al. (2023) compiled 26 principles for writing instructions (for example, being specific, stating the audience and constraining the output), and Sahoo et al. (2024) surveyed prompt-engineering techniques across tasks. Liu et al. (2024) found that models use information at the beginning and end of long contexts better than in the middle, which informs how many retrieved passages we include in the prompt.")
P("Reliability is the third thread. Ji et al. (2023) surveyed hallucination in natural language generation and documented its types and mitigation methods. Gao et al. (2023) surveyed retrieval-augmented generation, in which retrieved documents ground the answer; this is the approach we use for the FAQ. For evaluation, Zhang et al. (2024) benchmarked LLMs on news summarisation and found that instruction-tuned LLM summaries are rated on par with human-written ones, even though reference-based metrics rate them low, while Zheng et al. (2023) validated strong LLMs as judges of other model outputs. The Gemini Team (2023) describes the multimodal model family from which the API used here is drawn.")
P("Common trends are that engineered prompts improve accuracy and format compliance, that grounding reduces hallucination, and that reference-overlap metrics under-rate good abstractive text. The limitations are that most studies use English benchmarks rather than domain chat data, rarely report consistency, and seldom test false-premise questions. This project addresses that gap for the movie domain at a micro scale.")
table("Summary of reviewed studies", ["Study (year)", "Problem addressed", "Technique", "Key finding"], [
    ["Ouyang et al. (2022)", "Following user instructions", "RLHF fine-tuning (InstructGPT)", "Aligned models preferred over larger unaligned ones"],
    ["Wei et al. (2022)", "Multi-step reasoning", "Chain-of-thought prompting", "Large gains on reasoning benchmarks"],
    ["Kojima et al. (2022)", "Reasoning without examples", "Zero-shot CoT trigger phrase", "Simple phrase unlocks reasoning"],
    ["Wang et al. (2023)", "Unstable reasoning", "Self-consistency (majority vote)", "Improves CoT accuracy"],
    ["Min et al. (2022)", "Role of demonstrations", "Few-shot ablations", "Format and label space matter most"],
    ["Yao et al. (2023)", "Reasoning plus acting", "ReAct", "Tool use reduces hallucination"],
    ["Bsharat et al. (2023)", "Prompt-writing guidance", "26 principled instructions", "Specific, constrained prompts help"],
    ["Sahoo et al. (2024)", "Overview of prompting", "Systematic survey", "Taxonomy of techniques by task"],
    ["Liu et al. (2024)", "Use of long context", "Position analysis", "Middle-of-context information is under-used"],
    ["Ji et al. (2023)", "Hallucination", "Survey of NLG", "Types, causes and mitigations"],
    ["Gao et al. (2023)", "Grounding LLMs", "RAG survey", "Retrieval improves factuality"],
    ["Zhang et al. (2024)", "News summarisation", "Human evaluation of LLMs", "LLM summaries rated on par with human-written"],
    ["Zheng et al. (2023)", "Evaluating chat models", "LLM-as-a-judge", "Strong LLM judges agree well with humans"]],
    widths=[1.3, 1.5, 1.6, 2.0])

# ---------------------------------------------------------------- 3 methodology
H1("3. Proposed Methodology")
P("The workflow runs from the user message to a post-processed reply, with a separate evaluation harness that reuses the same prompt builder so that what is measured is exactly what the chatbot runs.")
H2("3.1 Overall System Architecture")
P("A user message enters the Streamlit chat. A keyword router selects the task (Q&A by default; “summarize”, “review:” and “genre” trigger the others) or the user chooses it manually. The prompt builder then assembles a system message and prompt from the strategy template, retrieving FAQ entries for Q&A. The LLM API returns text, which is parsed (label extraction) and shown with a tag of the task and strategy used.")
figure(RES / "architecture.png", "Architecture of CineBot (re-draw in draw.io or Canva for the final submission if required)")
H2("3.2 Dataset")
P(f"Two custom datasets were created. (a) FAQ dataset: {nfaq} question–answer pairs on film terminology, rating systems (MPA, CBFC), awards, festivals, review platforms and distribution. Answers are short, factual and written for this project. (b) Custom query set (data/queries.json) in four parts:")
table("Custom query set", ["Part", "Items", "Content", "Gold standard"], [
    ["Q&A", len(Q["qa"]), "6 FAQ paraphrases, 5 world-knowledge facts, 4 unanswerable or false-premise", "Reference answer or expected abstention"],
    ["Summarisation", len(Q["summarize"]), "Original 80–110-word synopses of well-known films", "One-sentence reference summary"],
    ["Sentiment", len(Q["sentiment"]), "Short custom-written reviews", "positive / negative / neutral"],
    ["Genre", len(Q["genre"]), "Short custom-written plot blurbs", "8 genre labels"]], widths=[1.1, .6, 3.0, 1.8])
P("Sample record: Q: “Which prize is the highest honour at Cannes?” Reference: “The Palme d’Or is the top prize at the Cannes Film Festival.” The data are small by design (a micro project) and written by the author, so there is no licensing issue; the synopses are original paraphrases, not copied text.")
H2("3.3 Data Preprocessing")
P("Text is used as raw natural language, because the LLM handles tokenisation itself. For retrieval and scoring the following steps are applied: lower-casing, tokenisation on alphanumeric tokens, English stop-word removal and unigram–bigram extraction for TF-IDF retrieval; for model outputs, label parsing with a regular expression (JSON “label” field or first matching label word, with “science fiction” normalised to “sci-fi”) and an abstention detector for phrases such as “I don’t know”.")
H2("3.4 Feature Engineering")
P("The only learned representation is a TF-IDF vector (1–2-grams) over each FAQ question and answer. The top three entries by cosine similarity to the user question are inserted into the RAG prompt. TF-IDF is suitable here because the FAQ is small, the vocabulary is specific (certificates, awards) and exact term overlap is a strong relevance signal; it needs no GPU or embedding API.")
H2("3.5 Model Development")
P(f"The LLM is {R['model'] if R else 'Google Gemini 2.5 Flash (configurable in .env)'}, called through its REST API. No training is performed; the work is in the prompts. Table 4 lists the strategies.")
table("Prompt strategies per task", ["Task", "Baseline", "Engineered strategies"], [
    ["Q&A", "zero_shot: raw question", "role_constraints: persona, ≤2 sentences, never invent, say “I don’t know” if unsure; rag: same rules plus top-3 retrieved FAQ entries"],
    ["Summarise", "zero_shot: “Summarize this…”", "constrained: exactly one sentence ≤25 words, name main character and conflict; few_shot: constrained plus two worked examples"],
    ["Sentiment / Genre", "zero_shot: open question", "few_shot: label set, one-word output, four examples; cot_json: brief reasoning then JSON {reasoning, label}"]], widths=[1.1, 1.8, 3.6])
P("Validation: each (task, strategy, item) is generated several times at temperature 0.7, so that both average quality and run-to-run variability are measured.")
H2("3.6 Proposed Novelty")
P("The novelty is the measurement layer rather than a new model: a consistency score for every prompt strategy, and an abstention test with unanswerable and false-premise questions, combined with retrieval-grounded prompting in a domain chatbot.")

# ---------------------------------------------------------------- 4 setup
H1("4. Experimental Setup")
P("Software: Python 3.13, requests (API calls), scikit-learn (TF-IDF, macro-F1), pandas, NumPy, matplotlib, Streamlit and python-docx. Hardware: Apple Silicon laptop (CPU only, 16 GB RAM, macOS); the LLM runs on the provider’s servers. Settings: "
  f"temperature {R['temperature'] if R else 0.7}, {R['repeats'] if R else 3} repeated generations per item, maximum 400 output tokens, API rate limited to 10 requests per minute for the free tier. Responses are cached on disk so that runs are resumable. Run: python evaluate.py.")

# ---------------------------------------------------------------- 5 results
H1("5. Results and Discussion")
H2("5.1 Performance Evaluation and Comparative Analysis")
P("Metrics. Q&A: token F1 and ROUGE-L against the reference on answerable questions; abstention accuracy on unanswerable ones (1 minus the hallucination rate); wrong-abstain rate on answerable ones. Summarisation: ROUGE-1, ROUGE-L, share of outputs within 25 words, and compression ratio. Classification: accuracy, macro-F1 and invalid-output rate. Consistency: for classification, the share of repeated runs that agree with the most common label; for text, the mean pairwise ROUGE-L between repeated outputs.")
table("Question answering", ["Strategy", "F1", "ROUGE-L", "Abstain acc.", "Wrong abstain", "Consistency", "Avg words"],
      [[s, val("qa", s, "f1"), val("qa", s, "rougeL"), val("qa", s, "abstain_acc"), val("qa", s, "wrong_abstain"), val("qa", s, "consistency"), val("qa", s, "avg_words", "{:.1f}")] for s in STRATEGIES["qa"]], widths=[1.4, .6, .8, .9, .9, .9, .7])
table("Summarisation", ["Strategy", "ROUGE-1", "ROUGE-L", "≤25 words", "Compression", "Consistency", "Avg words"],
      [[s, val("summarize", s, "rouge1"), val("summarize", s, "rougeL"), val("summarize", s, "within_25"), val("summarize", s, "compression"), val("summarize", s, "consistency"), val("summarize", s, "avg_words", "{:.1f}")] for s in STRATEGIES["summarize"]], widths=[1.4, .8, .8, .8, .9, .9, .7])
for t, name in (("sentiment", "Sentiment classification"), ("genre", "Genre classification")):
    table(name, ["Strategy", "Accuracy", "Macro-F1", "Invalid rate", "Consistency"],
          [[s, val(t, s, "accuracy"), val(t, s, "macro_f1"), val(t, s, "invalid_rate"), val(t, s, "consistency")] for s in STRATEGIES[t]], widths=[1.6, 1, 1, 1, 1])
if R:
    figure(RES / "strategy_comparison.png", "Quality and consistency of each prompt strategy", 6.2)
    P("Observations: [[Write 4–6 sentences: which strategy won per task, whether consistency rose with constraints, which questions caused hallucination, and any invalid outputs. Use all_outputs.csv for examples.]]")
else:
    P("[[Results pending: add your Gemini key to .env, run python evaluate.py (about 35 to 45 minutes on the free tier), then python build_report.py. The tables, chart and abstract fill automatically.]]")
H2("5.2 Output Screens and Result Demonstration")
P("[[Insert 3–4 screenshots from streamlit run app.py: (1) a Q&A answer with RAG, (2) a summarised synopsis, (3) a sentiment/genre label, (4) the “show prompt” expander. Caption each as Figure N.]]")

# ---------------------------------------------------------------- 6-8
H1("6. Comparative Analysis")
P("The baseline for every task is the plain zero-shot prompt. The comparison in Tables 5 to 8 isolates the effect of each prompt-engineering technique under the same model and settings. Role and constraint prompts are expected to shorten answers and improve format compliance; few-shot prompts to improve label validity; retrieval to improve factual agreement with the FAQ; and reasoning prompts to help on ambiguous reviews at the price of more tokens and latency. [[After running, state which of these expectations held and which did not.]]")
H1("7. Discussion of Errors and Evaluation Validity")
P("Reference-overlap metrics such as F1 and ROUGE reward lexical similarity and under-score correct answers that are worded differently, a known limitation of n-gram metrics for abstractive text (Zhang et al., 2024). For this reason the numbers should be read as a relative comparison between strategies, not as absolute quality. Abstention is detected with a phrase list, which can miss unusual refusals. With few items per task, a difference of one or two items can change accuracy by several points.")
H1("8. Ethical Considerations")
P("A chatbot that answers confidently can spread wrong film facts, so CineBot is instructed to abstain when unsure and shows which task and strategy produced each answer. User text is sent to a third-party API, so personal data should not be entered. Reviews used for evaluation are written by the author, so no real user content is reproduced.")

# ---------------------------------------------------------------- 9-12
H1("9. Limitations")
B("Small, author-written datasets (39 evaluation items); results have wide confidence intervals.")
B("Single LLM and single temperature; findings may not transfer to other models.")
B("Overlap metrics instead of human or LLM-judge scoring.")
B("Facts in the FAQ and references were written by the author and could contain errors; the model may also rely on knowledge newer or older than the FAQ.")
B("Free-tier rate limits make large-scale evaluation slow.")
H1("10. Future Scope")
B("Add LLM-as-a-judge scoring and human ratings.")
B("Scale to public datasets such as IMDb reviews and TMDB or Wikipedia plot summaries.")
B("Embedding-based retrieval, multi-turn memory, and Hindi or multilingual support.")
B("Live data via tool calling (showtimes, ratings) and a deployed public web app.")
B("Compare several LLMs, including an open-weight local model.")
H1("11. Conclusion")
P("CineBot shows how one LLM API can serve a movie-domain chatbot across question answering, summarisation and classification, and how prompt engineering can be compared systematically rather than by intuition. The project designed nine task-specific prompt templates, built a retrieval-grounded FAQ answerer, implemented an evaluation harness that scores both quality and consistency, and delivered an interactive chatbot. "
  + ("The measured results (Chapter 5) identify the best strategy per task. " if R else "[[One sentence on the measured results after running the evaluation.]] ")
  + "The work meets the stated objectives: prompts were designed for three task types, responses were generated through an LLM API, quality and consistency were evaluated, and performance was improved and compared using prompt-engineering techniques. The main lessons are that clear constraints, examples and grounding matter, and that evaluation must include unanswerable questions and repeated runs. The approach can be applied to other domains with a different FAQ and query set.")
H1("12. References")
for r in [
    "Bsharat, S. M., Myrzakhan, A., & Shen, Z. (2023). Principled instructions are all you need for questioning LLaMA-1/2, GPT-3.5/4. arXiv:2312.16171.",
    "Gao, Y., et al. (2023). Retrieval-augmented generation for large language models: A survey. arXiv:2312.10997.",
    "Gemini Team, Google. (2023). Gemini: A family of highly capable multimodal models. arXiv:2312.11805.",
    "Ji, Z., et al. (2023). Survey of hallucination in natural language generation. ACM Computing Surveys, 55(12), 1–38.",
    "Kojima, T., Gu, S. S., Reid, M., Matsuo, Y., & Iwasawa, Y. (2022). Large language models are zero-shot reasoners. NeurIPS 35.",
    "Liu, N. F., et al. (2024). Lost in the middle: How language models use long contexts. Transactions of the ACL, 12, 157–173.",
    "Min, S., et al. (2022). Rethinking the role of demonstrations: What makes in-context learning work? Proceedings of EMNLP 2022.",
    "Ouyang, L., et al. (2022). Training language models to follow instructions with human feedback. NeurIPS 35.",
    "Sahoo, P., et al. (2024). A systematic survey of prompt engineering in large language models: Techniques and applications. arXiv:2402.07927.",
    "Wang, X., et al. (2023). Self-consistency improves chain of thought reasoning in language models. ICLR 2023.",
    "Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. NeurIPS 35.",
    "Yao, S., et al. (2023). ReAct: Synergizing reasoning and acting in language models. ICLR 2023.",
    "Zhang, T., Ladhak, F., Durmus, E., Liang, P., McKeown, K., & Hashimoto, T. B. (2024). Benchmarking large language models for news summarization. Transactions of the ACL, 12, 39–57.",
    "Zheng, L., et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. NeurIPS 36 (Datasets and Benchmarks).",
    "Pedregosa, F., et al. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830."]:
    p = P(r); p.paragraph_format.left_indent = Inches(.4); p.paragraph_format.first_line_indent = Inches(-.4)
P("[[Check each citation's venue, volume and pages on the publisher or arXiv page before submitting.]]", align="l")
out = ROOT / "CineBot_NLP_CA3_Report.docx"
doc.save(out); print("saved", out, "| results:", "real" if R else "placeholders")
