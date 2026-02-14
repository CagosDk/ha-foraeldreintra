FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

COPY app.py /app/app.py

RUN pip install --no-cache-dir flask beautifulsoup4

EXPOSE 8080

CMD ["python", "/app/app.py"]
