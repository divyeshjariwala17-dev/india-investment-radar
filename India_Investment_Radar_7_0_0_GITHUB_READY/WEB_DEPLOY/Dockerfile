FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY payload/ /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY WEB_DEPLOY/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8501
ENTRYPOINT ["/entrypoint.sh"]
