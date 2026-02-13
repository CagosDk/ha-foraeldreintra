ARG BUILD_FROM=mcr.microsoft.com/playwright/python:v1.42.0-jammy
FROM $BUILD_FROM

WORKDIR /app

COPY app.py /app/app.py

RUN pip install --no-cache-dir flask beautifulsoup4

CMD ["python3", "/app/app.py"]
