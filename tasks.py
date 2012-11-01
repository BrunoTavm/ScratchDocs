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
list.add_argument('--iteration',dest='iteration')

gen = subparsers.add_parser('index')
gen.add_argument('--iteration',dest='iteration')

html = subparsers.add_parser('makehtml')
html.add_argument('--iteration',dest='iteration')
html.add_argument('--notasks',dest='notasks',action='store_true')

nw = subparsers.add_parser('new')
nw.add_argument('--iteration',dest='iteration')
nw.add_argument('--parent',dest='parent')
nw.add_argument('--summary',dest='summary')
nw.add_argument('--assignee',dest='assignee')
nw.add_argument('--id',dest='id')

purge = subparsers.add_parser('purge')
purge.add_argument('tasks',nargs='+')
purge.add_argument('--force',dest='force',action='store_true')

show = subparsers.add_parser('show')
show.add_argument('tasks',nargs='+')

move = subparsers.add_parser('move')
move.add_argument('fromto',nargs='+')

args = parser.parse_args()

def move_task(task,dest_iter):
    t = get_task(task)
    if t['iteration']==dest_iter:
        return False
    iterations = get_iterations()
    assert dest_iter in [i[0] for i in iterations],"%s not in %s"%(dest_iter,iterations)
    taskdir = os.path.dirname(t['path'])
    cmd = 'mv %s %s'%(taskdir,dict(iterations)[dest_iter])
    st,op = gso(cmd) ; assert st==0,"could not %s: %s"%(cmd,op)
    #print cmd
    return True
def purge_task(task,force=False):
    t = get_task(task)
    dn = os.path.dirname(t['path'])
    assert os.path.isdir(dn)
    ch = get_children(task)
    if len(ch) and not force:
        raise Exception('will not purge task with children unless --force is used.')
    st,op = gso('rm -rf %s'%dn) ; assert st==0
    return True

def pfn(fn):
    if cfg.CONSOLE_FRIENDLY_FILES:
        return 'file://%s'%os.path.abspath(fn)
    else:
        return fn

def parse_story_fn(fn,read=False):
    assert len(fn)
    parts = fn.replace(cfg.DATADIR,'').split(cfg.STORY_SEPARATOR)
    assert len(parts)>1,"%s"%"error parsing %s"%fn
    it = parts[1]
    story = cfg.STORY_SEPARATOR.join(parts[2:-1])
    rt = {'iteration':it,'story':story,'path':fn}
    if read:
        import orgparse
        root = orgparse.load(fn)
        for node in root[1:]:
            heading = node.get_heading()
            rt['summary']=heading
            break
        #storycont = open(
    return rt
def get_task_files(iteration=None):
    if iteration:
        itcnd=' -wholename "%s*"'%(os.path.join(cfg.DATADIR,str(iteration)))
    else:
        itcnd=''
    cmd = "find %s -maxdepth 3 %s -type f -name '%s'"%(cfg.DATADIR,itcnd,cfg.TASKFN)
    st,op = gso(cmd) ;assert st==0,"%s => %s"%(cmd,op)
    files = [fn for fn in op.split('\n') if fn!='']
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
def get_task(number,read=False):
    tf = [parse_story_fn(fn,read=read) for fn in get_task_files()]
    tasks = dict([(pfn['story'],pfn) for pfn in tf])    
    assert number in tasks
    rt =  tasks[number]
    return rt
def get_children(number):
    t = get_task(number)
    cmd = 'find %s -maxdepth 2 -type f -iname "%s" ! -wholename "%s"'%(os.path.dirname(t['path']),cfg.TASKFN,t['path'])
    st,op = gso(cmd) ; assert st==0
    chfiles = [ch for ch in op.split('\n') if ch!='']
    tf = [parse_story_fn(fn,read=True) for fn in chfiles]
    return tf
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
    files = [fn for fn in op.split('\n') if fn!='']
    
    tf = [parse_story_fn(fn) for fn in files]
    finalnames = [int(t['story'].split(cfg.STORY_SEPARATOR)[-1]) for t in tf]
    if len(finalnames):
        maxid = max(finalnames)
    else:
        maxid=0
    newid = maxid+1
    return str(newid)

        
def add_task(iteration=None,parent=None,params={},force_id=None):
    if not iteration: 
        if parent:
            t = get_task(parent)
            iteration = t['iteration']
        else:
            iteration = cfg.BACKLOG
    if parent:
        #make sure that parent is in iteration
        tf = [parse_story_fn(fn) for fn in get_task_files(iteration=iteration)]
        iterationtasks = dict([(tpfn['story'],tpfn) for tpfn in tf])
        assert parent in iterationtasks
        basedir = os.path.dirname(iterationtasks[parent]['path'])
        if force_id:
            newidx = force_id
        else:
            newidx = get_new_idx(parent=parent)
        newdir = os.path.join(basedir,newidx)
        newtaskfn = os.path.join(newdir,'task.org')
    else:
        basedir = os.path.join(cfg.DATADIR,iteration)
        if force_id:
            #make sure we don't have it already
            tf = [parse_story_fn(fn)['story'] for fn in get_task_files()]
            assert str(force_id) not in tf,"task %s already exists - %s."%(force_id,get_task(force_id))
            newidx = str(force_id)
        else:
            newidx = get_new_idx()
        newdir = os.path.join(basedir,newidx)
        newtaskfn = os.path.join(newdir,'task.org')
    newtaskdt = parse_story_fn(newtaskfn)
    assert newtaskdt
    print 'creating new task %s : %s'%(newtaskdt['story'],pfn(newtaskfn))
    assert not os.path.exists(newdir)
    st,op = gso('mkdir -p %s'%newdir) ; assert st==0,"could not mkdir %s"%newdir
    tpl = Template(open('templates/task.org').read())
    pars = params.__dict__
    pars['story_id'] = newidx
    pars['created'] = datetime.datetime.now()
    pars['creator'] = cfg.CREATOR
    pars['status'] = cfg.STATUSES[0]
    for k in ['summary','assignee','points','detail']:
       if k not in pars: pars[k]=None
    taskcont = tpl.render(**params.__dict__)
    assert not os.path.exists(taskcont)
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
        #print 'cycling through iteration %s'%it[0]
        if args.iteration and str(it[0])!=str(args.iteration): 
            #print 'skipping iteration %s'%(it[0])
            continue
        #print 'walking iteration %s'%it[0]
        taskfiles = get_task_files(iteration=it[0])
        stories = [(fn,parse_story_fn(fn,read=True)) for fn in taskfiles]

        vardict = {'iteration':it,'stories':stories}
        stlist = sttpl.render(**vardict)
        itidxfn = os.path.join(cfg.DATADIR,it[0],'index.org')

        fp = open(itidxfn,'w') ; fp.write(open(os.path.join(cfg.DATADIR,it[0],'iteration.org')).read()) ; fp.write(stlist) ; fp.close()
        
        print 'written iteration idx %s'%pfn(itidxfn)

        for st in stories:
            #storycont = open( st[0],'r').read()
            storyidxfn = os.path.join(os.path.dirname(st[0]),'index.org')
            #print storyidxfn
            ch = get_children(st[1]['story'])
            for c in ch:
                c['relpath']=os.path.dirname(c['path'].replace(os.path.dirname(st[1]['path'])+'/',''))
            print 'written story idx %s'%pfn(storyidxfn)
            tidxpl = Template(open('templates/taskindex.org').read())            
            pars = {'children':ch,'story':st[1],'TASKFN':cfg.TASKFN}
            idxcont = tidxpl.render(**pars)
            #print idxcont
            fp = open(storyidxfn,'w') ; fp.write(idxcont) ; fp.write(open(st[1]['path']).read()) ; fp.close()
if args.command=='makehtml':
    #find all the .org files generated
    if args.iteration:
        pth = os.path.join(cfg.DATADIR,args.iteration)
    else:
        pth = cfg.DATADIR
    st,op = gso('find %s -iname "*.org" -type f'%(pth)) ; assert st==0
    orgfiles = [fn for fn in op.split('\n') if fn!='']
    cnt=0
    for orgf in orgfiles:
        cnt+=1
        if args.notasks and (os.path.basename(orgf)==cfg.TASKFN or os.path.exists(os.path.join(os.path.dirname(orgf),cfg.TASKFN))):
            continue
        cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(orgf)
        outfile = os.path.join(os.path.dirname(orgf),os.path.basename(orgf).replace('.org','.html'))
        needrun=False
        if os.path.exists(outfile):
            sts = os.stat(orgf)
            stt = os.stat(outfile)
            if sts.st_mtime>stt.st_mtime:
                needrun=True
        else:
            needrun=True
        #print('needrun %s on %s'%(needrun,outfile))
        if needrun:
            st,op = gso(cmd) ; assert st==0,"%s returned %s"%(cmd,op)
            print 'written %s'%pfn(outfile)
        assert os.path.exists(outfile)
    print 'processed %s orgfiles.'%cnt


if args.command=='new':
    task = add_task(iteration=args.iteration,parent=args.parent,params=args,force_id=args.id)
if args.command=='purge':
    for task in args.tasks:
        purge_task(task,bool(args.force))
if args.command=='show':
    for task in args.tasks:
        t = get_task(task)
        print t
if args.command=='move':
    tasks = args.fromto[0:-1]
    dest = args.fromto[-1]
    for task in tasks:
        move_task(task,dest)
