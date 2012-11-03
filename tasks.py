#!/usr/bin/env python
import argparse
import config as cfg
from commands import getstatusoutput as gso
from prettytable import PrettyTable
import os
from mako.template import Template
from mako.lookup import TemplateLookup
import datetime
import orgparse
import hashlib
import re

if not os.path.exists(cfg.MAKO_DIR): os.mkdir(cfg.MAKO_DIR)
_prefix = os.path.dirname(__file__)
tpldir = os.path.join(_prefix,'templates')
lk = TemplateLookup(directories=['.'])
task_tpl = Template(filename=(os.path.join(tpldir,'task.org')),lookup = lk,module_directory=cfg.MAKO_DIR)
iterations_tpl = Template(filename=os.path.join(tpldir,'iterations.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
tasks_tpl = Template(filename=os.path.join(tpldir,'tasks.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
taskindex_tpl = Template(filename=os.path.join(tpldir,'taskindex.org'),lookup = lk,module_directory=cfg.MAKO_DIR)            
iteration_tpl = Template(filename=os.path.join(tpldir,'iteration.org'),lookup = lk,module_directory=cfg.MAKO_DIR)            
ckre = re.compile('^'+re.escape('<!-- checksum:')+'([\d\w]{32})'+re.escape(' -->'))
def md5(fn):
    st,op = gso('md5sum %s'%fn); assert st==0
    op = op.split(' ')
    return op[0]

def render(tplname,params,outfile=None,mode='w'):
    tpls = {'task':task_tpl
            ,'tasks':tasks_tpl
            ,'taskindex':taskindex_tpl
            ,'iterations':iterations_tpl
            ,'iteration':iteration_tpl
            }

    t = tpls[tplname]
    r= t.render(**params)
    if outfile:
        fp = open(outfile,mode) ; fp.write(r) ; fp.close()
        #print 'written %s %s'%(tplname,pfn(outfile))

        return True
    return t

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

def parse_attrs(node):
    rt= dict([a[2:].split(' :: ') for a in node.split('\n') if a.startswith('- ')])
    for k,v in rt.items():
        if k.endswith('date'):
            rt[k]=datetime.datetime.strptime(v.strip('<>[]'),'%Y-%m-%d')
        if k in ['created at']:
            rt[k]=datetime.datetime.strptime(v.strip('<>[]').split('.')[0],'%Y-%m-%d %H:%M:%S')
    return rt
def parse_story_fn(fn,read=False):
    assert len(fn)
    parts = fn.replace(cfg.DATADIR,'').split(cfg.STORY_SEPARATOR)
    assert len(parts)>1,"%s"%"error parsing %s"%fn
    it = parts[1]
    story = cfg.STORY_SEPARATOR.join(parts[2:-1])
    rt = {'iteration':it,'story':story,'path':fn}
    if read:
        root = orgparse.load(fn)
        heading=None
        for node in root[1:]:
            if not heading:
                heading = node.get_heading()
                rt['summary']=heading
            elif node.get_heading()=='Attributes':
                attrs = parse_attrs(unicode(node))
                for k,v in attrs.items():
                    rt[k]=v
                    if k=='tags':
                        rt[k]=v.split(', ')


        #storycont = open(
    return rt
def get_task_files(iteration=None,assignee=None,status=None,tag=None,recurse=True,recent=False):
    if iteration:
        itcnd=' -wholename "%s/*"'%(os.path.join(cfg.DATADIR,str(iteration)))
    else:
        itcnd=''
    if not recurse:
        add=' -maxdepth 3'
    else:
        add=''
    cmd = "find  %s  %s ! -wholename '*templates*' ! -wholename '*.git*' %s -type f -name '%s'"%(cfg.DATADIR,add,itcnd,cfg.TASKFN)
    st,op = gso(cmd) ;assert st==0,"%s => %s"%(cmd,op)
    files = [fn for fn in op.split('\n') if fn!='']

    #filter by assignee. heavy.
    if assignee or status or tag or recent:
        rt = []
        for fn in files:
            s = parse_story_fn(fn,read=True)
            incl=False
            if assignee and s['assigned to'] and s['assigned to']==assignee:
                incl=True
            if status and s['status']==status:
                incl=True
            if tag and 'tags' in s and tag in s['tags']:
                incl=True
            if recent and 'created at' in s and s['created at']>=(datetime.datetime.now()-datetime.timedelta(days=cfg.RECENT_DAYS)):
                incl=True
            if incl:
                rt.append(fn)
        return rt
            
    return files

def sort_iterations(i1,i2):
    try:i1v = i1[1]['end date']
    except KeyError: 
        i1v = datetime.datetime.now()+datetime.timedelta(days=3650)
    try: i2v = i2[1]['end date'] #int(i2[0])
    except KeyError: 
        i2v = datetime.datetime.now()+datetime.timedelta(days=3650)
        
    rt= cmp(i1v,i2v)
    return rt
def status_srt(s1,s2):
    cst = dict([(cfg.STATUSES[i],i) for i in range(len(cfg.STATUSES))])
    return cmp(cst[s1[1]['status']],cst[s2[1]['status']])
def taskid_srt(s1,s2):
    cst = dict([(cfg.STATUSES[i],i) for i in range(len(cfg.STATUSES))])
    s1i = int(s1[1]['story'].split(cfg.STORY_SEPARATOR)[0])
    s2i = int(s2[1]['story'].split(cfg.STORY_SEPARATOR)[0])
    return cmp(s1i,s2i)
def parse_iteration(pth):
    iteration_name = os.path.basename(os.path.dirname(pth))
    rt={'path':pth,'name':os.path.basename(os.path.dirname(pth))}
    root = orgparse.load(pth)
    for node in root[1:]:
        head = node.get_heading()
        if node.get_heading()=='Attributes':
            attrs = parse_attrs(unicode(node))
            for k,v in attrs.items(): rt[k]=v
    return rt
def get_iterations():
    cmd = 'find %s -name "iteration.org" ! -wholename "*templates*" -type f'%(cfg.DATADIR)
    #cmd = 'find %s -maxdepth 1 ! -wholename "*.git*"  -type d'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0
    #print op  ; raise Exception('w00t')
    dirs = op.split('\n')
    rt = [(os.path.dirname(path),parse_iteration(path)) for path in dirs if len(path.split('/'))>1]
    rt.sort(sort_iterations,reverse=True)
    return rt
def get_task(number,read=False,exc=True):
    number = str(number)
    tf = [parse_story_fn(fn,read=read) for fn in get_task_files()]
    tasks = dict([(pfn['story'],pfn) for pfn in tf])    
    if exc:
        assert number in tasks
    else:
        if number not in tasks: 
            return False
    rt =  tasks[number]
    return rt
def get_children(number):
    t = get_task(number)
    cmd = 'find %s -maxdepth 2 ! -wholename "*.git*" -type f -iname "%s" ! -wholename "%s"'%(os.path.dirname(t['path']),cfg.TASKFN,t['path'])
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
    findcmd = 'find %s -maxdepth %s ! -wholename "*.git*" -type f -iname "%s" %s'%(tpath,md,cfg.TASKFN,add)
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

        
def add_task(iteration=None,parent=None,params={},force_id=None,tags=[]):
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
    pars = params.__dict__
    pars['story_id'] = newidx
    pars['created'] = datetime.datetime.now()
    pars['creator'] = cfg.CREATOR
    pars['status'] = cfg.STATUSES[0]

    for k in ['summary','assignee','points','detail']:
       if k not in pars: pars[k]=None

    assert not os.path.exists(newdir),"%s exists"%newdir
    st,op = gso('mkdir -p %s'%newdir) ; assert st==0,"could not mkdir %s"%newdir

    assert not os.path.exists(newtaskfn)
    render('task',params.__dict__,newtaskfn)

def makehtml(iteration=None,notasks=False,files=[]):
    #find all the .org files generated

    if iteration:
        pth = os.path.join(cfg.DATADIR,iteration)
    else:
        pth = cfg.DATADIR
    findcmd = 'find %s ! -wholename "*orgparse*" ! -wholename "*templates*" ! -wholename "*.git*" -iname "*.org" -type f'%(pth)
    st,op = gso(findcmd) ; assert st==0

    if len(files):
        orgfiles = files
    else:
        orgfiles = [fn for fn in op.split('\n') if fn!='']
    cnt=0
    for orgf in orgfiles:
        cnt+=1
        if notasks and (os.path.basename(orgf)==cfg.TASKFN or os.path.exists(os.path.join(os.path.dirname(orgf),cfg.TASKFN))):
            continue
        outfile = os.path.join(os.path.dirname(orgf),os.path.basename(orgf).replace('.org','.html'))
        needrun=False
        if os.path.exists(outfile): #emacs is darn slow.
            #invalidate by checksum
            st,op = gso('tail -1 %s'%outfile) ; assert st==0
            res = ckre.search(op)
            if res and os.path.exists(orgf): 
                ck = res.group(1)
                md = md5(orgf)
                if ck!=md:
                    needrun=True
            else:
                needrun=True
        else:
            needrun=True
        #print('needrun %s on %s'%(needrun,outfile))
        if needrun:
            cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(orgf)
            st,op = gso(cmd) ; assert st==0,"%s returned %s"%(cmd,op)
            print 'written %s'%pfn(outfile)

            if os.path.exists(orgf):
                md = md5(orgf)
                apnd = '\n<!-- checksum:%s -->'%(md)
                fp = open(outfile,'a') ; fp.write(apnd) ; fp.close()

        assert os.path.exists(outfile)

    print 'processed %s orgfiles.'%cnt

def by_status(stories):
    rt = {}
    for s in stories:
        st = s[1]['status']
        if st not in rt: rt[st]=[]
        rt[st].append(s)
    return rt
def makeindex(iteration):

    iterations = get_iterations()
    iterations_stories={}

    #find out the current one
    nw = datetime.datetime.now() ; current_iteration=None
    for itp,it in iterations:
        if ('start date' in it and 'end date' in it):
            if (it['start date']<=nw and it['end date']>=nw):
                current_iteration = (itp,it)
    recent = [(tf,parse_story_fn(tf,read=True)) for tf in get_task_files(recent=True)]

        
    assignees={}
    for it in iterations:
        #print 'cycling through iteration %s'%it[0]
        if iteration and str(it[1]['name'])!=str(iteration): 
            #print 'skipping iteration %s'%(it[0])
            continue
        #print 'walking iteration %s'%it[0]
        taskfiles = get_task_files(iteration=it[1]['name'],recurse=True)
        stories = [(fn,parse_story_fn(fn,read=True)) for fn in taskfiles]
        stories.sort(taskid_srt,reverse=True)        
        shallowstories = [st for st in stories if len(st[1]['story'].split(cfg.STORY_SEPARATOR))==1]
        iterations_stories[it[1]['name']]=len(shallowstories)

        vardict = {'term':'Iteration','value':it[0],'stories':by_status(shallowstories),'relpath':True,'statuses':cfg.STATUSES,'iteration':False} #the index is generated only for the immediate 1-level down stories.
        itidxfn = os.path.join(cfg.DATADIR,it[0],'index.org')
        fp = open(itidxfn,'w') ; fp.write(open(os.path.join(cfg.DATADIR,it[0],'iteration.org')).read()) ; fp.close()
        stlist = render('tasks',vardict,itidxfn,'a') 

        #we show an iteration index of the immediate 1 level down tasks

        for st in shallowstories:
            #aggregate assignees
            if st[1]['assigned to']:
                asgn = st[1]['assigned to']
                if asgn not in assignees: assignees[asgn]=0
                assignees[asgn]+=1

            #storycont = open( st[0],'r').read()
            storyidxfn = os.path.join(os.path.dirname(st[0]),'index.org')
            #print storyidxfn
            ch = get_children(st[1]['story'])
            for c in ch:
                c['relpath']=os.path.dirname(c['path'].replace(os.path.dirname(st[1]['path'])+'/',''))
            #print 'written story idx %s'%pfn(storyidxfn)

            pars = {'children':ch,'story':st[1],'TASKFN':cfg.TASKFN}
            render('taskindex',pars,storyidxfn,'w')
            fp = open(storyidxfn,'a') ; fp.write(open(st[1]['path']).read()) ; fp.close()

            #print idxcont
    assigned_files={}
    for asfn in ['alltime','current']:
        for assignee,storycnt in assignees.items():
            afn = 'assigned-'+assignee+'-'+asfn+'.org'
            ofn = os.path.join(cfg.DATADIR,afn)
            if assignee not in assigned_files: assigned_files[assignee]={}
            assigned_files[assignee][asfn]=afn
            if asfn=='current' and current_iteration:
                f_iter = current_iteration[1]['name']
            else:
                f_iter=None
            tf = get_task_files(assignee=assignee,recurse=True,iteration=f_iter)
            stories = [(fn,parse_story_fn(fn,read=True)) for fn in tf]
            stories.sort(status_srt)
            vardict = {'term':'Assignee','value':'%s (%s)'%(assignee,storycnt),'stories':by_status(stories),'relpath':False,'statuses':cfg.STATUSES,'iteration':True}
            cont = render('tasks',vardict,ofn)


    vardict = {'iterations':iterations,
               'iterations_stories':iterations_stories,
               'assigned_files':assigned_files,
               'assignees':assignees,
               'current_iteration':current_iteration,
               'recent_tasks':recent
               }
    idxfn = os.path.join(cfg.DATADIR,'index.org')
    itlist = render('iterations',vardict,idxfn)

def list_stories(iteration=None,assignee=None,status=None,tag=None,recent=False):
    files = get_task_files(iteration=iteration,assignee=assignee,status=status,tag=tag,recent=recent)
    pt = PrettyTable(['iteration','id','summary','assigned to','status','tags','fn'])
    pt.align['summary']='l'
    cnt=0
    for fn in files:
        sd = parse_story_fn(fn,read=True)
        if iteration and sd['iteration']!=str(iteration): continue
        if len(sd['summary'])>40: summary=sd['summary'][0:40]+'..'
        else: summary = sd['summary']
        pt.add_row([sd['iteration'],sd['story'],summary,sd['assigned to'],sd['status'],','.join(sd.get('tags','')),pfn(sd['path'])])
        cnt+=1
    pt.sortby = 'status'
    print pt
    print '%s stories.'%cnt

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Task Control',prog='tasks.py')
    subparsers = parser.add_subparsers(dest='command')

    list = subparsers.add_parser('list')
    list.add_argument('--iteration',dest='iteration')
    list.add_argument('--assignee',dest='assignee')
    list.add_argument('--status',dest='status')
    list.add_argument('--tag',dest='tag')
    list.add_argument('--recent',dest='recent',action='store_true')

    gen = subparsers.add_parser('index')
    gen.add_argument('--iteration',dest='iteration')

    html = subparsers.add_parser('makehtml')
    html.add_argument('--iteration',dest='iteration')
    html.add_argument('--notasks',dest='notasks',action='store_true')
    html.add_argument('files',nargs='*')

    nw = subparsers.add_parser('new')
    nw.add_argument('--iteration',dest='iteration')
    nw.add_argument('--parent',dest='parent')
    nw.add_argument('--summary',dest='summary')
    nw.add_argument('--assignee',dest='assignee')
    nw.add_argument('--id',dest='id')
    nw.add_argument('--tag',dest='tags',action='append')

    purge = subparsers.add_parser('purge')
    purge.add_argument('tasks',nargs='+')
    purge.add_argument('--force',dest='force',action='store_true')

    show = subparsers.add_parser('show')
    show.add_argument('tasks',nargs='+')

    move = subparsers.add_parser('move')
    move.add_argument('fromto',nargs='+')

    args = parser.parse_args()

    if args.command=='list':
        list_stories(iteration=args.iteration,assignee=args.assignee,status=args.status,tag=args.tag,recent=args.recent)
    if args.command=='index':
        makeindex(args.iteration)
    if args.command=='makehtml':
        makehtml(iteration=args.iteration,notasks=args.notasks,files=args.files)

    if args.command=='new':
        task = add_task(iteration=args.iteration,parent=args.parent,params=args,force_id=args.id,tags=args.tags)
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
