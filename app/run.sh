#!/bin/bash

LOGFOLDER="log"
LOGFILE="$LOGFOLDER/scale.log"

mkdir -p "$LOGFOLDER"
date >> "$LOGFILE"

# Appending Redirected Output
exec >> "$LOGFILE" 2>&1

echo "Starting DYMO Scale Gateway..."
python main.py
