# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import Response


from tasks import parse_story_fn as parse_fn
from tasks import get_task_files as get_fns
from tasks import get_task,get_children,get_iterations,iteration_srt,get_participants,rewrite,get_new_idx,add_task,get_current_iteration,get_participants,initvars,move_task,get_parent,flush_taskfiles_cache,tasks_validate,get_table_contents
from config import STATUSES,RENDER_URL,DATADIR,URL_PREFIX,NOPUSH,NOCOMMIT
from noodles.templates import render_to
from noodles.http import Redirect
from commands import getstatusoutput as gso
from multiprocessing import Process
import datetime
from tasks import loadmeta
from tasks import parsegitdate
import os
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
    pts = get_participants(sort=True)
    return {'pts':pts}

def get_parent_descriptions(tid):
    #obtain parent descriptions
    parents = tid.split('/')
    opar=[]
    for i in xrange(len(parents)-1): opar.append('/'.join(parents[:i+1]))
    parents = [(pid,get_task(pid,read=True)['summary']) for pid in opar]
    return parents

@render_to('index.html')
def iterations(request):
    its = get_iterations()
    return {'its':its,'cur':get_current_iteration(its)}

def asgn(request,person=None,iteration=None,recurse=True,notdone=False,query=None):
    in_tasks = [parse_fn(fn,read=True,gethours=True,hoursonlyfor=person) for fn in get_fns(assignee=person,iteration=iteration,recurse=recurse,query=query)]
    tasks={}
    for t in in_tasks:
        tlp = get_parent(t['id'],tl=True)
        partasks = [stask for stask in in_tasks if stask['id']==tlp]
        st = t['status']
        #print 'st of %s setting to status of tlp %s: %s'%(t['id'],tlp,st) 
        if st not in tasks: tasks[st]=[]

        t['pdescrs']=get_parent_descriptions(t['id'])

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

def assignments_itn_func(request,person=None,iteration=None,mode='normal',query=None):
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
    rt=asgn(request,person=person,iteration=curn,notdone=notdone,query=query)
    rt['headline']=headline
    return rt

@render_to('iteration.html')
def assignments_itn(request,person,iteration,mode='normal'):
    return assignments_itn_func(request,person,iteration,mode)

@render_to('iteration.html')
def index(request):
    iteration =         cur = get_current_iteration(get_iterations())
    curn = cur[1]['name']
    return assignments_itn_func(request
                                ,get_admin(request,'unknown')
                                ,iteration=curn
                                ,mode='notdone')


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

@render_to('iteration_time.html')
def iteration_time(request,iteration):
    its = get_iterations()
    it = [it for it in its if it[1]['name']==iteration][0]
    start_date = it[1]['start date'].date()
    end_date = it[1]['end date'].date()
    tf = get_fns(iteration=iteration,recurse=True)
    hours = [os.path.join(os.path.dirname(t),'hours.json') for t in tf]
    agg={} ; persons={} ; ptasks={}
    for h in hours:
        tid = '/'.join(os.path.dirname(h).split('/')[2:])
        if not os.path.exists(h): continue
        md = loadmeta(h)
        for stmp,data in md.items():
            stmp = datetime.datetime.strptime(stmp,'%Y-%m-%d').date()
            if not (stmp>=start_date and stmp<=end_date): continue
            for person,hours in data.items():
                if stmp not in agg: agg[stmp]={}
                if person not in agg[stmp]: agg[stmp][person]={}
                if person not in persons: persons[person]=0
                if person not in ptasks: ptasks[person]=[]
                persons[person]+=hours
                if tid not in ptasks[person]: ptasks[person].append(tid)
                if tid not in agg[stmp][person]: agg[stmp][person][tid]=0
                agg[stmp][person][tid]+=hours
    agg = list(agg.items())
    agg.sort(lambda i1,i2: cmp(i1[0],i2[0]))
    persons = list(persons.items())
    persons.sort(lambda i1,i2: cmp(i1[1],i2[1]),reverse=True)
    return {'persons':persons,'agg':agg,'it':it,'ptasks':ptasks}

@render_to('iteration_commits.html')
def iteration_commits(request,iteration,branch):
    gwu = cfg.GITWEB_URL
    its = get_iterations()
    it = [it for it in its if it[1]['name']==iteration][0]
    start_date = it[1]['start date']
    end_date = it[1]['end date']
    print('commits on iteration %s to branch %s'%(iteration,branch))
    tf = get_fns(iteration=iteration,recurse=True)
    metas = [os.path.join(os.path.dirname(t),'meta.json') for t in tf]
    agg={} ; repos=[] ; task_data={} ; lastcommits={}
    
    for m in metas:
        tid = '/'.join(os.path.dirname(m).split('/')[2:])
        if not os.path.exists(m): continue
        md = loadmeta(m)
        if 'branchlastcommits' not in md: continue
        blc = md['branchlastcommits']

        for br,stmp in blc.items():
            if  '/' not in br:
                print "%s has no /"%(br)
                continue
            try:
                repo,br = br.split('/')
            except ValueError:
                print '%s has too many /'%(br)
                continue
            stmp = parsegitdate(stmp)
            if not (stmp.date()>=start_date.date() and stmp.date()<=end_date.date()):
                #print 'bad commit date %s'%stmp
                continue
            if not (branch=='all' or branch==br):
                #print 'branch mismatch %s<>%s'%(branch,br)
                continue
            if tid not in agg:
                agg[tid]={}
            if repo not in agg[tid]:
                agg[tid][repo]=[]
            agg[tid][repo].append(br)

            if tid not in task_data:
                t = get_task(tid,read=True)
                task_data[tid]=t

            if tid not in lastcommits: lastcommits[tid]=stmp
            if stmp>=lastcommits[tid]: lastcommits[tid]=stmp

            if repo not in repos: repos.append(repo)
            #print(tid,repo,br,stmp)
    agg = list(agg.items())
    def lcsort(i1,i2):
        return cmp(lastcommits[i1[0]],lastcommits[i2[0]])
    agg.sort(lcsort,reverse=True)
    return {'agg':agg,'it':it,'branch':branch,'repos':repos,'gwu':gwu,'task_data':task_data,'lastcommits':lastcommits}
    #raise Exception(metas)

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
    st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)
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
    
    repos = [r['Name'] for r in get_table_contents('repos.org')]

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
                links.append({'url':v,'anchor':unicode(tn,'utf-8')})
        if k.startswith('informed-'):
            tn = k.replace('informed-','')
            if tn=='new': continue
            informed.append(tn)
        if k.startswith('repobranch-'):
            tn = k.replace('repobranch-','')
            if tn in ['new-repo','new-branch']: continue
            repobranch.append(tn)
    lna = request.params.get('link-new-anchor')
    lnu = request.params.get('link-new-url')
    if lna and lnu:
        links.append({'anchor':lna,'url':lnu})

    inn = request.params.get('informed-new')
    if inn and inn not in informed:
        informed.append(inn)

    nrb = request.params.get('repobranch-new-branch')
    if nrb: repobranch.append(request.params.get('repobranch-new-repo')+'/'+nrb)


    tags = list(set([tag for tag in tags if tag!='']))

    uns = request.params.get('unstructured','').strip()
    if len(uns) and not uns.startswith('**'):
        uns='** Details\n'+uns
    if request.params.get('id'):
        t = get_task(request.params.get('id'),read=True,flush=True)
        tid = request.params.get('id')

        o_params = {'summary':request.params.get('summary'),
                    'tags':tags,
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':uns,
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
                    'creator':get_admin(request,'unknown'),
                    'unstructured':uns,
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
        opar=[]
    else:
        t = get_task(task,read=True,flush=True,gethours=True)
        par = task ; parents=[]
        parents = task.split('/')
        opar = []
        for i in xrange(len(parents)-1):
            opar.append('/'.join(parents[:i+1]))
    parents = [(pid,get_task(pid,read=True)['summary']) for pid in opar]
    prt = [r[0] for r in get_participants(sort=True)]
    return {'task':t,'gwu':gwu,'url':RENDER_URL,'statuses':STATUSES,'participants':prt,'iterations':[i[1]['name'] for i in get_iterations()],'msg':msg,'children':ch,'repos':repos,'parents':parents}


@render_to('iteration.html')
def search(request):
    return assignments_itn_func(request
                                ,person=None
                                ,iteration=None
                                ,mode='normal'
                                ,query=request.params.get('q'))


