ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ttf-freefont

# Set workdir
WORKDIR /app

# Copy files
COPY app.py /app/app.py
COPY run.sh /app/run.sh

# Install Python deps
RUN pip3 install --no-cache-dir flask beautifulsoup4 playwright

# Install browser
RUN playwright install chromium

# Make script executable
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
