import datetime
from couchdbkit import *
from couchdbkit.designer import push
from docs import get_fns,initvars,get_task,parse_fn,read_journal
import config as cfg    
import sys
import json

# Wrap sys.stdout into a StreamWriter to allow writing unicode.
import codecs
import locale
sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout) 
# done

initvars(cfg)

from couchdb import Task,init_conn,push_views

def get_task(tid):
    return Task.get(tid)

def get_children(tid):
    ints = [int(tp) for tp in tid.split('/')]
    sk = ints
    ek = ints+[{}]
    tasks = Task.view('task/children',
                      startkey=sk,
                      endkey=ek)
    return [t for t in tasks if t._id!=tid]

def get_parents(tid):
    ints = [int(tp) for tp in tid.split('/')]
    keys=[]
    for l in range(1,len(ints)):
        keys.append(ints[0:l])    
    tasks = Task.view('task/children',
                      keys=keys,
                      )
    return tasks

if __name__=='__main__':
    s,d = init_conn()
    
    #push_views(d)

    tid = sys.argv[1]

    
    t = get_task(tid) #Task.view('task/all',key=tid)
    print 'QUERIED TASK:'
    print t._id,t.summary


    tasks = get_children(tid)

    print len(tasks),'CHILDREN'
    for t in tasks: 
        print t.path,t._id,t.summary,','.join(t.tags)


    tasks = get_parents(tid)
    print len(tasks),'PARENTS'
    for t in tasks:
        print t.path,t._id,t.summary,','.join(t.tags)
    #print 'done'
