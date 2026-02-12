FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

COPY app.py /app/app.py

RUN pip install flask beautifulsoup4

CMD ["python3", "/app/app.py"]
