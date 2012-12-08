# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import Response


from tasks import parse_story_fn as parse_fn
from tasks import get_task_files as get_fns
from tasks import get_task,get_children,get_iterations,iteration_srt,get_participants,rewrite,get_new_idx,add_task,get_current_iteration,get_participants,initvars
from config import STATUSES,RENDER_URL,DATADIR,URL_PREFIX,NOPUSH,NOCOMMIT
from noodles.templates import render_to
from noodles.http import Redirect
from commands import getstatusoutput as gso
from multiprocessing import Process
import config as cfg
import re
from config_local import WEBAPP_FORCE_IDENTITY as force_identity

initvars(cfg)
def get_admin(r,d):

    if force_identity:
        return force_identity
    if not r.headers.get('Authorization'):
        return d
        #raise AuthErr('no authorization found')

    username = re.compile('username="([^"]+)"').search(r.headers.get('Authorization'))
    if username:
        rt= username.group(1)
        rt = rt.split('@')[0].replace('.','_')
        return rt
    return d

@render_to('participants.html')
def participants(request):
    pts = get_participants()
    return {'pts':pts}

@render_to('index.html')
def iterations(request):
    its = get_iterations()
    return {'its':its,'cur':get_current_iteration(its)}

def asgn(request,person=None,iteration=None,recurse=True):
    in_tasks = [parse_fn(fn,read=True) for fn in get_fns(assignee=person,iteration=iteration,recurse=recurse)]
    tasks={}
    for st in STATUSES:
        tasks[st] = [t for t in in_tasks if t['status']==st]
        tasks[st].sort(iteration_srt)
    return {'tasks':tasks,'statuses':STATUSES}

@render_to('iteration.html') 
def assignments(request,person):
    rt= asgn(request,person)
    rt['headline']='Assignments for %s'%person
    return rt

@render_to('iteration.html')
def assignments_current(request,person):
    cur = get_current_iteration(get_iterations())
    rt=asgn(request,person=person,iteration=cur[1]['name'])
    rt['headline']='Current assignments for %s'%person
    return rt

@render_to('iteration.html')
def index(request):
    cur = get_current_iteration(get_iterations())
    adm = get_admin(request,'unknown')
    rt= asgn(request,adm,iteration=cur[1]['name'])
    rt['headline']='Current assignments.'
    return rt

@render_to('iteration.html')
def iteration(request,iteration):
    rt = asgn(request,iteration=iteration,recurse=False)
    rt['headline']='Iteration %s'%iteration
    return rt

def pushcommit(pth,tid,adm):
    pts = get_participants()
    commiter = pts[adm]
    def push():
        print 'starting push'
        st,op = gso('cd %s && git pull && git push'%(DATADIR))
        if not st % 256==0:
            print "git push returned %s\n%s"%(st,op)
            raise Exception('greenlet exception') 
        print op
        print 'done push'
    #push in the background!
    if not NOCOMMIT:
        cmd = 'cd %s && git add %s && git commit --author="%s" -m "webapp update of %s"'%(DATADIR,pth,"%s <%s>"%(commiter['Name'],commiter['E-Mail']),tid)
        print cmd
        st,op = gso(cmd) ; assert st% 256==0,"%s returned %s\n%s"%(cmd,st,op)
        msg='Updated task %s'%tid
    if not NOPUSH:
        p = Process(target=push)
        p.start()

@render_to('task.html')
def task(request,task):
    msg=None
    adm = get_admin(request,'unknown')

    if request.params.get('id'):
        t = get_task(request.params.get('id'),read=True,flush=True)
        tid = request.params.get('id')
        tags=[]
        for k,v in request.params.items():
            if k.startswith('tag-'):
                tn = k.replace('tag-','')
                if tn=='new':
                    for nt in [nt.strip() for nt in v.split(',') if nt.strip()!='']:
                        tags.append(nt)
                else:
                    tags.append(tn)
        tags = list(set([tag for tag in tags if tag!='']))

        o_params = {'summary':request.params.get('summary'),
                    'tags':tags,
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':request.params.get('unstructured').strip()}
        print o_params
        rewrite(tid,o_params,safe=False)
        pushcommit(t['path'],request.params.get('id'),adm)
    if request.params.get('create'):
        o_params = {'summary':request.params.get('summary'),
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':request.params.get('unstructured').strip()}
        rt = add_task(iteration='Backlog',params=o_params)
        redir = '/'+URL_PREFIX+'task/'+rt['story_id']
        pushcommit(rt['path'],rt['story_id'],adm)
        print 'redircting to %s'%redir
        rd = Redirect(redir)
        return rd
    if task=='new':
        t = {'story':'','id':None,'created at':None,'summary':'','unstructured':'','iteration':'Backlog','status':'TODO','assigned to':adm,'created by':adm,'tags':[]}
    else:
        t = get_task(task,read=True,flush=True)
    return {'task':t,'url':RENDER_URL,'statuses':STATUSES,'participants':get_participants(),'iterations':[i[1]['name'] for i in get_iterations()],'msg':msg}
