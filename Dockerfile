FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
COPY supermarket_app/requirements.txt ./supermarket_app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY .streamlit/config.toml ./.streamlit/config.toml
COPY supermarket_app/ ./supermarket_app/
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
ENV PORT=8501 PYTHONUNBUFFERED=1
EXPOSE 8501
CMD ["sh", "supermarket_app/run_cloud.sh"]
