ARG BUILD_FROM
FROM $BUILD_FROM

LABEL \
  io.hass.name="ForældreIntra Scraper" \
  io.hass.description="Scraper SkoleIntra via Playwright" \
  io.hass.type="addon"

# Install dependencies
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

RUN pip3 install --no-cache-dir flask beautifulsoup4 playwright

RUN playwright install chromium

CMD ["python3", "/app/app.py"]
