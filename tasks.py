from celery import Celery
from time import sleep
import logging
from docs import get_participants
import config as cfg
from docs import initvars
import config as cfg
import subprocess
initvars(cfg)
from docs import gso
    
celery = Celery('tasks',broker='redis://localhost')


@celery.task
def pushcommit(pth,tid,adm):

    pts = get_participants()
    commiter = pts[adm]

    if not cfg.NOCOMMIT:
        
        cmd = 'cd %s && git add %s && git add -u && git commit --author="%s" -m "webapp update of %s"'%(cfg.DATADIR,pth,"%s <%s>"%(commiter['Name'],commiter['E-Mail']),tid)
        cmd = 'cd %s'%cfg.DATADIR
        print cmd
        st,op = gso(cmd,shell=True,executable='/bin/bash')  ; assert st% 256==0,"%s returned %s\n%s"%(cmd,st,op)
        msg='Updated task %s'%tid

    def push():
        print 'starting push'
        st,op = gso('cd %s && git pull && git push'%(cfg.DATADIR),shell=True)
        if not st % 256==0:
            print "git push returned %s\n%s"%(st,op)
            raise Exception('greenlet exception') 
        print op
        print 'done push'

    if not cfg.NOPUSH:
        push()
