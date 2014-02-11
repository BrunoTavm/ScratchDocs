from celery import Celery
from time import sleep
import logging
from docs import get_participants,get_changes,process_notifications
import config as cfg
from docs import initvars
import config as cfg
import subprocess
initvars(cfg)
from commands import getstatusoutput as gso
    
celery = Celery('tasks',broker='redis://localhost')


@celery.task
def pushcommit(pth,tid,adm):

    pts = get_participants()
    commiter = pts.get(adm)
    if not commiter:
        name = 'Unknown'
        email = 'Uknown'
    else:
        name = commiter['Name']
        email = commiter['E-Mail']
    if type(pth)==list:
        pths = ' '.join(pth)
    else:
        pths = pth
    if not cfg.NOCOMMIT:
        
        cmd = 'cd %s && git add %s && git add -u && git commit --author="%s" -m "webapp update of %s"'%(cfg.DATADIR,pths,"%s <%s>"%(name,email),tid)
        st,op = gso(cmd)  ; assert st% 256==0,"%s returned %s\n%s"%(cmd,st,op)
        msg='Updated task %s'%tid

    def push():
        print 'starting push'
        st,op = gso('cd %s && git pull && git push'%(cfg.DATADIR))
        if not st % 256==0:
            print "git push returned %s\n%s"%(st,op)
            raise Exception('greenlet exception') 
        print op
        print 'done push'

    if not cfg.NONOTIFY:
        get_changes(show=False,add_notifications=True,changes_limit=1)
        process_notifications(adm=adm)

    if not cfg.NOPUSH:
        push()

from tasks import get_changes

@celery.task
def changes_to_feed():
    get_changes(show=False,feed=True)



