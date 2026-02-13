#!/usr/bin/with-contenv bashio

export SKOLE_USERNAME=$(bashio::config 'username')
export SKOLE_PASSWORD=$(bashio::config 'password')
export SCHOOL_URL=$(bashio::config 'school_url')

python3 /app/app.py
