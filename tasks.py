#!/usr/bin/env python
import argparse
import config as cfg
from commands import getstatusoutput as gso
from prettytable import PrettyTable
import os
from mako.template import Template
import datetime

parser = argparse.ArgumentParser(description='Task Control',prog='tasks.py')
subparsers = parser.add_subparsers(dest='command')

list = subparsers.add_parser('list')
list.add_argument('--teration',dest='iteration')

gen = subparsers.add_parser('index')

nw = subparsers.add_parser('new')
nw.add_argument('--iteration',dest='iteration')
nw.add_argument('--parent',dest='parent')
nw.add_argument('--summary',dest='summary')
nw.add_argument('--assignee',dest='assignee')

args = parser.parse_args()

def pfn(fn):
    if cfg.CONSOLE_FRIENDLY_FILES:
        return 'file://%s'%os.path.abspath(fn)
    else:
        return fn

def parse_story_fn(fn):
    parts = fn.replace(cfg.DATADIR,'').split(cfg.STORY_SEPARATOR)
    it = parts[1]
    story = cfg.STORY_SEPARATOR.join(parts[2:-1])
    return {'iteration':it,'story':story,'path':fn}

def get_task_files(iteration=None):
    if iteration:
        itcnd=' -wholename "%s*"'%(os.path.join(cfg.DATADIR,str(iteration)))
    else:
        itcnd=''
    cmd = "find %s %s -type f -name '%s'"%(cfg.DATADIR,itcnd,cfg.TASKFN)
    st,op = gso(cmd) ;assert st==0,"%s => %s"%(cmd,op)
    files = op.split('\n')
    return files

def sort_iterations(i1,i2):
    try:i1v = int(i1[0])
    except ValueError: i1v = 1000
    try: i2v = int(i2[0])
    except ValueError: i2v = 1000
        
    rt= cmp(i1v,i2v)
    return rt
def get_iterations():
    cmd = 'find %s  -maxdepth 1 -type d'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0
    #print op  ; raise Exception('w00t')
    dirs = op.split('\n')
    rt = [(os.path.basename(path),path) for path in dirs if len(path.split('/'))>1]
    rt.sort(sort_iterations,reverse=True)
    return rt
def get_task(number):
    tf = [parse_story_fn(fn) for fn in get_task_files()]
    tasks = dict([(pfn['story'],pfn) for pfn in tf])    
    assert number in tasks
    return tasks[number]

def get_new_idx(parent=None):
    if parent:
        t = get_task(parent)
        tpath = os.path.dirname(t['path'])
        md = 2
        add = ' ! -wholename "%s"'%t['path']
    else:
        tpath = cfg.DATADIR
        md = 3
        add = ''
    findcmd = 'find %s -maxdepth %s -type f -iname "%s" %s'%(tpath,md,cfg.TASKFN,add)
    st,op = gso(findcmd) ; assert st==0
    files = op.split('\n')
    tf = [parse_story_fn(fn) for fn in files]
    finalnames = [int(t['story'].split(cfg.STORY_SEPARATOR)[-1]) for t in tf]
    maxid = max(finalnames)
    newid = maxid+1
    return str(newid)

        
def add_task(iteration=None,parent=None,params={}):
    if not iteration: iteration = cfg.BACKLOG
    if parent:
       #make sure that parent is in iteration
       tf = [parse_story_fn(fn) for fn in get_task_files(iteration=iteration)]
       iterationtasks = dict([(tpfn['story'],tpfn) for tpfn in tf])
       assert parent in iterationtasks
       basedir = os.path.dirname(iterationtasks[parent]['path'])
       newidx = get_new_idx(parent=parent)
       newdir = os.path.join(basedir,newidx)
       newtaskfn = os.path.join(newdir,'task.org')
    else:
        basedir = os.path.join(cfg.DATADIR,iteration)
        newidx = get_new_idx()
        newdir = os.path.join(basedir,newidx)
        newtaskfn = os.path.join(newdir,'task.org')
    newtaskdt = parse_story_fn(newtaskfn)
    assert newtaskdt
    print 'creating new task %s : %s'%(newtaskdt['story'],pfn(newtaskfn))
    st,op = gso('mkdir -p %s'%newdir) ; assert st==0
    tpl = Template(open('templates/task.org').read())
    pars = params.__dict__
    pars['story_id'] = newidx
    pars['created'] = datetime.datetime.now()
    pars['creator'] = cfg.CREATOR
    pars['status'] = cfg.STATUSES[0]
    for k in ['summary','assignee','points','detail']:
       if k not in pars: pars[k]=None
    taskcont = tpl.render(**params.__dict__)
    fp = open(newtaskfn,'w') ; fp.write(taskcont) ; fp.close()
    
def list_stories(iteration=None):
    files = get_task_files(iteration=iteration)
    pt = PrettyTable(['iteration','id'])
    cnt=0
    for fn in files:
        sd = parse_story_fn(fn)
        if iteration and sd['iteration']!=str(iteration): continue
        pt.add_row([sd['iteration'],sd['story']])
        cnt+=1
    print pt
    print '%s stories.'%cnt
if args.command=='list':
    list_stories(iteration=args.iteration)
if args.command=='index':
    iterations = get_iterations()
    tpl = Template(open('templates/iterations.org').read())
    vardict = {'iterations':iterations}
    itlist = tpl.render(**vardict)
    idxfn = os.path.join(cfg.DATADIR,'index.org')
    fp = open(idxfn,'w') ; fp.write(itlist) ; fp.close()
    print 'written main idx %s'%pfn(idxfn)
    sttpl = Template(open('templates/stories.org').read())
    for it in iterations:
        #print 'walking iteration %s'%it[0]
        taskfiles = get_task_files(iteration=it[0])
        stories = [(fn,parse_story_fn(fn)) for fn in taskfiles]
        vardict = {'iteration':it,'stories':stories}
        stlist = sttpl.render(**vardict)
        itidxfn = os.path.join(cfg.DATADIR,it[0],'index.org')
        fp = open(itidxfn,'w') ; fp.write(stlist) ; fp.close()
        print 'written iteration idx %s'%pfn(itidxfn)

        for st in stories:
            storycont = open( st[0],'r').read()
            storyidxfn = os.path.join(os.path.dirname(st[0]),'index.org')
            #print storyidxfn
            fp = open(storyidxfn,'w') ; fp.write(storycont) ; fp.close()
            print 'written story idx %s'%pfn(storyidxfn)

if args.command=='new':
    task = add_task(iteration=args.iteration,parent=args.parent,params=args)
