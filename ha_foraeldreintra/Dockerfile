FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

COPY app.py /app/app.py
COPY run.sh /app/run.sh

RUN chmod +x /app/run.sh
RUN pip install flask beautifulsoup4

CMD ["/app/run.sh"]
