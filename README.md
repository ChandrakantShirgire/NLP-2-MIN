# CineBot: movie chatbot with prompt engineering (NLP CA-3)

1. `cp .env.example .env` and paste your free Gemini key (https://aistudio.google.com/apikey)
2. `pip install -r requirements.txt`
3. `python evaluate.py`         (~35-45 min on free tier; resumable; writes results/)
4. `python build_report.py`     (fills tables, chart, abstract)
5. `streamlit run app.py`       (chatbot)
