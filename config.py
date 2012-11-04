DATADIR='data'
SHORTCUT_PREFIX='s'
OUTDIR='render'
TASKFN='task.org'
BACKLOG='Backlog'
STORY_SEPARATOR='/'
STATUSES=['TODO','DOING','REVIEW','DONE']
CONSOLE_FRIENDLY_FILES=True
RECENT_DAYS=14
MAKO_DIR='/tmp/mako_modules'
def USERMAP(un):
    return un
from config_local import *
import os
SDIR = os.path.join(DATADIR,SHORTCUT_PREFIX)
