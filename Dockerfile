FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
EXPOSE 8080
ENV PORT=8080
# Unbuffered stdout so print()/logs show up in `kubectl logs` immediately
# (Python block-buffers stdout when it isn't a TTY — a classic container gotcha).
ENV PYTHONUNBUFFERED=1
CMD ["python", "app/app.py"]
