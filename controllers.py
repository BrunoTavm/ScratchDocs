# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import Response


from tasks import parse_story_fn as parse_fn
from tasks import get_task_files as get_fns
from tasks import get_task,get_children,get_iterations,iteration_srt,get_participants,rewrite
from config import STATUSES,RENDER_URL,REPO_DIR
from noodles.templates import render_to
from commands import getstatusoutput as gso
from multiprocessing import Process

@render_to('index.html')
def iterations(request):
    its = get_iterations()
    return {'its':its}

def asgn(request,person):
    tasks = [parse_fn(fn,read=True) for fn in get_fns(assignee=person)]
    tasks.sort(iteration_srt)
    return {'tasks':tasks,'headline':'Assignments for %s'%person}

@render_to('iteration.html') 
def assignments(request,person):
    return asgn(request,person)

@render_to('iteration.html')
def index(request):
    return asgn(request,'guy')

@render_to('iteration.html')
def iteration(request,iteration):
    tasks = [parse_fn(fn,read=True) for fn in get_fns(iteration=iteration)]
    tasks.sort(iteration_srt)
    return {'tasks':tasks,'headline':'Iteration %s'%iteration}

@render_to('task.html')
def task(request,task):
    msg=None
    if request.params.get('id'):
        t = get_task(request.params.get('id'),read=True,flush=True)
        tid = request.params.get('id')
        o_params = {'summary':request.params.get('summary'),
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':request.params.get('unstructured')}
        rewrite(tid,o_params,safe=False)
        cmd = 'cd %s && git add %s && git commit -m "webapp update of %s"'%(REPO_DIR,t['path'],request.params.get('id'))
        st,op = gso(cmd) ; assert st% 256==0,"%s returned %s\n%s"%(cmd,st,op)
        msg='Updated task %s'%tid
        def push():
            print 'starting push'
            st,op = gso('cd %s && git pull && git push'%(REPO_DIR))
            if not st % 256==0:
                print "git push returned %s\n%s"%(st,op)
                raise Exception('greenlet exception') 
            print 'done push'
        #push in the background!
        p = Process(target=push)
        p.start()

    t = get_task(task,read=True,flush=True)
    
    return {'task':t,'url':RENDER_URL,'statuses':STATUSES,'participants':get_participants(),'iterations':[i[1]['name'] for i in get_iterations()],'msg':msg}
