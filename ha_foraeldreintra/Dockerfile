ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY app.py /app/app.py

RUN pip3 install --no-cache-dir --break-system-packages flask beautifulsoup4 requests

CMD ["python3", "/app/app.py"]
