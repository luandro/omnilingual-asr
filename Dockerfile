FROM python:3.11-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 build-essential cmake
RUN pip install --no-cache-dir torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
RUN pip install --no-cache-dir 'fairseq2[arrow]==0.6.0' --extra-index-url https://fair.pkg.atmeta.com/fairseq2/whl/pt2.8.0/cu126
COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src
RUN pip install --no-cache-dir . runpod==1.8.1 soundfile==0.13.1 && pip check
COPY deploy /app/deploy
RUN python deploy/prefetch.py
ENV MODEL_CARD=omniASR_CTC_1B_v2
CMD ["python", "-u", "deploy/handler.py"]
