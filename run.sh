#!/usr/bin/with-contenv bashio

export SKOLE_USERNAME=$(bashio::config 'username')
export SKOLE_PASSWORD=$(bashio::config 'password')

python3 /app/app.py
