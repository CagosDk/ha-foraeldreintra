ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ttf-freefont

WORKDIR /app

COPY app.py /app/app.py
COPY run.sh /run.sh

RUN chmod a+x /run.sh

RUN pip3 install --no-cache-dir --break-system-packages \
    flask \
    beautifulsoup4

CMD [ "/run.sh" ]
