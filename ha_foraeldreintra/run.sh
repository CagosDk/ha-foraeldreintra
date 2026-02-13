#!/bin/bash

export SKOLE_USERNAME="$USERNAME"
export SKOLE_PASSWORD="$PASSWORD"
export SCHOOL_URL="$SCHOOL_URL"

python3 /app/app.py
