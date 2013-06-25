import config as cfg
from tasks import get_task_files,get_task,parse_story_fn
from orm import *
import os
from commands import getstatusoutput as gso

def import_tasks():
    tf = get_task_files()
    tf.sort(lambda x,y: cmp(len(x),len(y)))

    for tfn in tf:
        dn = os.path.dirname(tfn)
        dnspl = [dnp for dnp in dn.split('/') if dnp!='.']
        iteration = dnspl[0]
        fqtid = '/'.join(dnspl[1:])
        tid = dnspl[-1]
        if len(dnspl)>2:
            ptid = dnspl[-2]
        else:
            ptid = None

        found = s.query(Task).filter(Task.fqtid==fqtid).all()
        if len(found):
            assert len(found)==1,"%s found for %s"%(len(found) ,fqtid)
            t = found[0]
        else:
            t = Task()
        t.fqtid = fqtid
        t.tid = tid
        t.ptid = ptid
        t.itn = iteration
        s.add(t) ; 
        print 'commiting %s'%fqtid
        s.commit()

