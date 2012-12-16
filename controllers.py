# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import Response


from tasks import parse_story_fn as parse_fn
from tasks import get_task_files as get_fns
from tasks import get_task,get_children,get_iterations,iteration_srt,get_participants,rewrite,get_new_idx,add_task,get_current_iteration,get_participants,initvars,move_task,get_parent,flush_taskfiles_cache,tasks_validate
from config import STATUSES,RENDER_URL,DATADIR,URL_PREFIX,NOPUSH,NOCOMMIT
from noodles.templates import render_to
from noodles.http import Redirect
from commands import getstatusoutput as gso
from multiprocessing import Process


import re
from config_local import WEBAPP_FORCE_IDENTITY as force_identity
import config as cfg
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

def asgn(request,person=None,iteration=None,recurse=True,notdone=False):
    in_tasks = [parse_fn(fn,read=True,gethours=True,hoursonlyfor=person) for fn in get_fns(assignee=person,iteration=iteration,recurse=recurse)]
    tasks={}
    for t in in_tasks:
        tlp = get_parent(t['id'],tl=True)
        partasks = [stask for stask in in_tasks if stask['id']==tlp]
        if len(partasks): # got parents here
            st = partasks[0]['status']
        else: #don't have all parents in context
            st = t['status']
        #print 'st of %s setting to status of tlp %s: %s'%(t['id'],tlp,st) 
        if st not in tasks: tasks[st]=[]

        showtask=False
        if not notdone: showtask=True
        if t['status']!='DONE': showtask=True
        if not showtask:
            chstates = set([chst['status'] for chst in get_children(t['id'])])
            if len(chstates)>1:
                showtask=True
            elif len(chstates)==1 and list(chstates)[0]!='DONE':
                showtask=True
            elif not len(chstates):
                pass
            else:
                pass
                #raise Exception(chstates,len(chstates))
        if showtask:
            tasks[st].append(t)
    for st in STATUSES:
        if st in tasks:
            tasks[st].sort(iteration_srt)
    return {'tasks':tasks,'statuses':STATUSES}

@render_to('iteration.html') 
def assignments(request,person):
    rt= asgn(request,person)
    rt['headline']='Assignments for %s'%person
    return rt

@render_to('iteration.html')
def assignments_itn(request,person,iteration,mode='normal'):
    if iteration=='current':
        cur = get_current_iteration(get_iterations())
        curn = cur[1]['name']
        headline = 'Current assignments for %s'%person
    else:        
        curn = iteration
        headline = 'Iteration %s assignments for %s'%(curn,person)
    notdone=False
    if mode=='notdone':
        notdone=True
        headline+='; Not Done.'
    rt=asgn(request,person=person,iteration=curn)
    rt['headline']=headline
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

@render_to('iteration.html')
def iteration_all(request,iteration):
    rt = asgn(request,iteration=iteration,recurse=True)
    rt['headline']='Iteration %s with all tasks'%iteration
    return rt

@render_to('iteration.html')
def iteration_notdone(request,iteration):
    rt = asgn(request,iteration=iteration,recurse=True,notdone=True)
    rt['headline']='Iteration %s with all tasks (and parents) that are not done'%iteration
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
        cmd = 'cd %s && git add %s && git add -u && git commit --author="%s" -m "webapp update of %s"'%(DATADIR,pth,"%s <%s>"%(commiter['Name'],commiter['E-Mail']),tid)
        print cmd
        st,op = gso(cmd) ; assert st% 256==0,"%s returned %s\n%s"%(cmd,st,op)
        msg='Updated task %s'%tid
    if not NOPUSH:
        p = Process(target=push)
        p.start()

def rpr(request,task):
    t= get_task(task)
    cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(t['path'])
    st,op = gso(cmd) ; assert st==0
    r = Response()
    r.body = open(t['path'].replace('.org','.html'),'r').read()
    return r

@render_to('task.html')
def task(request,task):
    gwu = cfg.GITWEB_URL
    if task.startswith('new/'):
        under='/'.join(task.split('/')[1:])
        task='new'
    else:
        under=None

    msg=None
    adm = get_admin(request,'unknown')
    
    
    tags=[] ; links=[] ; informed=[] ; repobranch=[]
    for k,v in request.params.items():
        if k.startswith('tag-'):
            tn = k.replace('tag-','')
            if tn=='new':
                for nt in [nt.strip() for nt in v.split(',') if nt.strip()!='']:
                    tags.append(nt)
            else:
                tags.append(tn)
        if k.startswith('link-'):
            tn = k.replace('link-','')
            if tn in ['new-url','new-anchor']:
                continue #raise Exception('newlink')
            else:
                links.append({'url':v,'anchor':tn})
        if k.startswith('informed-'):
            tn = k.replace('informed-','')
            if tn=='new': continue
            informed.append(tn)
        if k.startswith('repobranch-'):
            tn = k.replace('repobranch-','')
            if tn=='new': continue
            repobranch.append(tn)
    lna = request.params.get('link-new-anchor')
    lnu = request.params.get('link-new-url')
    if lna and lnu:
        links.append({'anchor':lna,'url':lnu})

    inn = request.params.get('informed-new')
    if inn and inn not in informed:
        informed.append(inn)

    nrb = request.params.get('repobranch-new')
    if nrb and '/' in nrb: repobranch.append(nrb)

    tags = list(set([tag for tag in tags if tag!='']))

    if request.params.get('id'):
        t = get_task(request.params.get('id'),read=True,flush=True)
        tid = request.params.get('id')

        o_params = {'summary':request.params.get('summary'),
                    'tags':tags,
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':request.params.get('unstructured').strip(),
                    'links':links,'informed':informed,'repobranch':repobranch}
        print o_params
        rewrite(tid,o_params,safe=False)
        t = get_task(tid,flush=True)
        dit = request.params.get('iteration')
        if t['iteration']!=dit and dit:
            move_task(tid,dit)
            flush_taskfiles_cache()
        t = get_task(tid,flush=True) #for the flush
        pushcommit(t['path'],request.params.get('id'),adm)
    if request.params.get('create'):
        o_params = {'summary':request.params.get('summary'),
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':request.params.get('unstructured').strip(),
                    'links':links,'informed':informed,'repobranch':repobranch}
        if request.params.get('under'):
            parent = request.params.get('under')
            iteration=None
        else:
            parent=None
            iteration=request.params.get('iteration')

        rt = add_task(parent=parent,iteration=iteration,params=o_params,tags=tags)
        redir = '/'+URL_PREFIX+'s/'+rt['id']
        pushcommit(rt['path'],rt['story_id'],adm)
        print 'redircting to %s'%redir
        rd = Redirect(redir)
        return rd
    if task=='new':
        ch=[]
    else:
        ch = get_children(task)
    if task=='new':
        t = {'story':'','id':None,'created at':None,'summary':'','unstructured':'','iteration':'Backlog','status':'TODO','assigned to':adm,'created by':adm,'tags':[],'under':under}
    else:
        t = get_task(task,read=True,flush=True,gethours=True)
            
    return {'task':t,'gwu':gwu,'url':RENDER_URL,'statuses':STATUSES,'participants':get_participants(),'iterations':[i[1]['name'] for i in get_iterations()],'msg':msg,'children':ch}
