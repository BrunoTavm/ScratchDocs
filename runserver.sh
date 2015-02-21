#!/bin/bash
SN='tasks'
tmux new-session -d -s "$SN"
tmux neww -t $SN -n server
tmux send-keys -t${SN} '. sd/venv/bin/activate ; while (true) ; do python sd/runserver.py ; done' C-m
tmux neww -t $SN -n worker
tmux send-keys -t${SN} '. sd/venv/bin/activate ; cd sd ; celery worker -A tasks --config celeryconfig' C-m
tmux attach-ses -t "$SN"