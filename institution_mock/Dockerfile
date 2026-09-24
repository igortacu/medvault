FROM python:3.11-slim

WORKDIR /app
COPY institution_mock/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY institution_mock /app/institution_mock

CMD ["uvicorn", "institution_mock.app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
