FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

COPY app.py /app/app.py

RUN pip install flask beautifulsoup4

CMD ["python3", "/app/app.py"]
