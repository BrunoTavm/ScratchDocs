DATADIR='data'
SHORTCUT_PREFIX='s'
OUTDIR='render'
TASKFN='task.org'
BACKLOG='Backlog'
STORY_SEPARATOR='/'
STATUSES=['REVIEW','DOING','TODO','DONE','DUPE','POSTPONED','CANCELLED'] 
DEFAULT_STATUS='TODO'
CONSOLE_FRIENDLY_FILES=True
RECENT_DAYS=14
MAKO_DIR='/tmp/mako_modules'
RENDER_URL=None
SENDER=None
GITWEB_URL=None
REPOSITORIES=[]
REPO_DIR='repos'
DOCS_REPONAME=None
TPLDIR='templates'
ALWAYS_INFORMED=[]
NOSEND=False
def USERMAP(un):
    return un
def COMMITERMAP(em,nm):
    assert '@' not in em
    assert '.' not in em
    return em
from noodles_config import *
from config_local import *
import os
SDIR = os.path.join(DATADIR,SHORTCUT_PREFIX)

