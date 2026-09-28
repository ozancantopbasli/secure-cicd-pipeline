FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser

COPY app.py .

EXPOSE 5000

USER appuser

CMD ["python", "app.py"]
