"""CineBot: movie chatbot with task routing and selectable prompt strategies. streamlit run app.py"""
import streamlit as st

from llm import LLM
from prompts import DEFAULT_STRATEGY, STRATEGIES, build, parse_label

st.set_page_config(page_title="CineBot", page_icon="🎬")
TASKS = {"Auto-detect": None, "Q&A": "qa", "Summarize a synopsis": "summarize", "Review sentiment": "sentiment", "Plot genre": "genre"}


def route(text):
    t = text.lower()
    if "summar" in t or "tl;dr" in t:
        return "summarize"
    if "sentiment" in t or "review:" in t:
        return "sentiment"
    if "genre" in t:
        return "genre"
    return "qa"


with st.sidebar:
    st.header("Settings")
    task_label = st.selectbox("Task", list(TASKS))
    use_best = st.checkbox("Use best-performing strategy", True)
    manual = st.selectbox("Prompt strategy", sorted({s for v in STRATEGIES.values() for s in v}), disabled=use_best)
    temp = st.slider("Temperature", 0.0, 1.0, 0.2, 0.1)
    show_prompt = st.checkbox("Show the prompt sent to the LLM", False)
    backend = st.selectbox("Backend", ["gemini", "mock"], help="mock = offline stub for testing the UI only")
    st.caption("Tip: paste a synopsis after 'Summarize:', a review after 'Review:', or a plot after 'Genre:'.")

st.title("🎬 CineBot")
st.caption("Movie FAQ · synopsis summaries · review sentiment · genre classification")
if "chat" not in st.session_state:
    st.session_state.chat = []
for m in st.session_state.chat:
    st.chat_message(m["role"]).write(m["content"])

if msg := st.chat_input("Ask about films, or paste a synopsis / review / plot…"):
    st.session_state.chat.append({"role": "user", "content": msg}); st.chat_message("user").write(msg)
    task = TASKS[task_label] or route(msg)
    body = msg.split(":", 1)[1].strip() if ":" in msg and task != "qa" else msg
    strat = DEFAULT_STRATEGY[task] if use_best else (manual if manual in STRATEGIES[task] else STRATEGIES[task][0])
    system, prompt = build(task, strat, body)
    try:
        out = LLM(backend=backend).generate(prompt, system, temperature=temp, max_tokens=500)
        if task in ("sentiment", "genre"):
            out = f"**{parse_label(task, out)}**" + ("" if strat != "cot_json" else f"\n\n{out}")
    except Exception as e:
        out = f"⚠️ {e}"
    tag = f"`{task}` · `{strat}`"
    with st.chat_message("assistant"):
        st.write(out); st.caption(tag)
        if show_prompt:
            st.code(((system + "\n\n") if system else "") + prompt, language="text")
    st.session_state.chat.append({"role": "assistant", "content": f"{out}\n\n{tag}"})
