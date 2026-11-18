FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY pages/ ./pages/
COPY fixtures/ ./fixtures/

ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true --browser.gatherUsageStats=false"]
