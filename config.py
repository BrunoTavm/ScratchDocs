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
HOST='0.0.0.0'
USE_ALCHEMY_MW=False
import logging
LOG_LEVEL=logging.WARNING
NOSEND=False
def USERMAP(un):
    return un
def COMMITERMAP(em,nm):
    assert '@' not in em
    assert '.' not in em
    return em
METASTATES={
    'functional review':('needed','doing','failed','passed'),
    'code review':('needed','doing','failed','passed'),
    'tests passage':('no','building','random fails','100%'),
    'merge to staging':('pending','merged'),
    }
METASTATES_COLORS={
    'needed':'orange',
    'doing':'yellow',
    'failed':'red',
    'passed':'green',
    'no':'grey',
    'random fails':'orange',
    'building':'orange',
    '100%':'green',
    'pending':'red',
    'merged':'green',
    '':'white'
    }
METASTATES_OVERRIDES={
    'merged':"""fullstates.get(k) and fullstates.get(k).get('updated') or ''"""
}
DIFF_BRANCHES=['staging','master'] #display diff links to gitweb for those baseline branches
from noodles_config import *
from config_local import *
import os
SDIR = os.path.join(DATADIR,SHORTCUT_PREFIX)

