DATADIR='data'
SHORTCUT_PREFIX='s'
OUTDIR='render'
TASKFN='task.org'
BACKLOG='Backlog'
STORY_SEPARATOR='/'
STATUSES=['REVIEW','DOING','TODO','DONE','DUPE','POSTPONED','CANCELLED'] 
DONESTATES=['DONE','DUPE','CANCELLED','POSTPONED']
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
NOCOMMIT=False
NOPUSH=False
NONOTIFY=False
import logging
LOG_LEVEL=logging.WARNING
def USERMAP(un):
    return un
def COMMITERMAP(em,nm):
    assert '@' not in em
    assert '.' not in em
    return em
METASTATES={
    'functional review':('needed','doing','failed','passed'),
    'code review':('needed','doing','failed','passed','client review'),
    'tests passage':('no','building','random fails','integrator','100%'),
    'merge to staging':('pending','merged','on production'),
    }
METASTATES_COLORS={
    'needed':'orange',
    'doing':'yellow',
    'failed':'red',
    'passed':'#0f0',
    'no':'#ddd',
    'random fails':'orange',
    'building':'orange',
    '100%':'#0f0',
    'pending':'red',
    'merged':'#0f0',
    'integrator':'yellow',
    '':'white',
    'client review':'cyan',
    'on production':'cyan',
    }
METASTATES_OVERRIDES={
    'merged':"""fullstates.get(k) and fullstates.get(k).get('updated').strftime('%Y-%m-%d %H:%M') or ''""",
    'passed':"""(fullstates.get(k) and 'by '+fullstates.get(k).get('updated by','')) or ''""",
}
DIFF_BRANCHES=['staging','master','production'] #display diff links to gitweb for those baseline branches
from noodles_config import *
from config_local import *
import os
SDIR = os.path.join(DATADIR,SHORTCUT_PREFIX)

