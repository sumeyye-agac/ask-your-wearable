# Optional reproducible build of the web app. The public app runs on Streamlit Community
# Cloud, which does not use this file; CI builds it and checks that the page starts.
#
#   docker build -t ask-your-wearable .
#   docker run --rm -p 8501:8501 -e ANTHROPIC_API_KEY=... ask-your-wearable
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the app reads at run time. The key is passed with -e, never copied in.
COPY streamlit_app.py .
COPY .streamlit/config.toml .streamlit/config.toml
COPY src src
COPY assets assets
COPY data/demo data/demo

RUN useradd --create-home app && mkdir logs && chown app logs
USER app

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
