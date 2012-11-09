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
import codecs
import json
import tempfile


if not os.path.exists(cfg.MAKO_DIR): os.mkdir(cfg.MAKO_DIR)
_prefix = os.path.dirname(__file__)
tpldir = os.path.join(_prefix,'templates')
lk = TemplateLookup(directories=['.'])
task_tpl = Template(filename=(os.path.join(tpldir,'task.org')),lookup = lk,module_directory=cfg.MAKO_DIR)
iterations_tpl = Template(filename=os.path.join(tpldir,'iterations.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
tasks_tpl = Template(filename=os.path.join(tpldir,'tasks.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
taskindex_tpl = Template(filename=os.path.join(tpldir,'taskindex.org'),lookup = lk,module_directory=cfg.MAKO_DIR)            
iteration_tpl = Template(filename=os.path.join(tpldir,'iteration.org'),lookup = lk,module_directory=cfg.MAKO_DIR)            
new_story_notify_tpl = Template(filename=os.path.join(tpldir,'new_story_notify.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
changes_tpl = Template(filename=os.path.join(tpldir,'changes.org'),lookup = lk,module_directory=cfg.MAKO_DIR)     
ckre = re.compile('^'+re.escape('<!-- checksum:')+'([\d\w]{32})'+re.escape(' -->'))
def md5(fn):
    st,op = gso('md5sum %s'%fn); assert st==0
    op = op.split(' ')
    return op[0]

commits = {}
commitsfn = os.path.join(cfg.DATADIR,'commits.json')
def loadcommits():
    global commits
    if not len(commits):
        if not os.path.exists(commitsfn):
            commits={}
        else:
            commits = json.load(open(commitsfn,'r'))
    return commits

    
def render(tplname,params,outfile=None,mode='w'):
    tpls = {'task':task_tpl
            ,'tasks':tasks_tpl
            ,'taskindex':taskindex_tpl
            ,'iterations':iterations_tpl
            ,'iteration':iteration_tpl
            ,'new_story_notify':new_story_notify_tpl
            ,'changes':changes_tpl
            }

    t = tpls[tplname]
    for par,val in params.items():
        try:
            if type(val)==str:
                val = unicode(val.decode('utf-8'))
                params[par]=val
        except:
            print val
            raise
    r= t.render(**params)
    if outfile:
        #print 'working %s'%outfile;        print params
        fp = codecs.open(outfile,mode,encoding='utf-8') ; fp.write(r) ; fp.close()
        #print 'written %s %s'%(tplname,pfn(outfile))

        return True
    return t

def move_task(task,dest_iter):
    t = get_task(task)
    if t['iteration']==dest_iter:
        return False
    iterations = get_iterations()
    assert dest_iter in [i[1]['name'] for i in iterations],"%s not in %s"%(dest_iter,iterations)
    taskdir = os.path.dirname(t['path'])
    iterdirs = dict([(i[1]['name'],os.path.dirname(i[1]['path'])) for i in iterations])
    cmd = 'mv %s %s'%(taskdir,iterdirs[dest_iter])
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
linkre = re.compile(re.escape('[[')+'([^\]]+)'+re.escape('][')+'([^\]]+)'+re.escape(']]'))
def parse_attrs(node):
    try:
        rt= dict([a[2:].split(' :: ') for a in node.split('\n') if a.startswith('- ') and ' :: ' in a])
        links=[]
        for a in node.split('\n'):
            res = linkre.search(a)
            if res:
                url,anchor = res.groups()
                links.append({'url':url,'anchor':anchor})
    except:
        print node.split('\n')
        raise
    for k,v in rt.items():
        if k.endswith('date'):
            rt[k]=datetime.datetime.strptime(v.strip('<>[]'),'%Y-%m-%d')
        if k in ['created at']:
            rt[k]=datetime.datetime.strptime(v.strip('<>[]').split('.')[0],'%Y-%m-%d %H:%M:%S')
    rt['links']=links
    return rt
def parse_story_fn(fn,read=False,gethours=False,hoursonlyfor=None):
    assert len(fn)
    parts = fn.replace(cfg.DATADIR,'').split(cfg.STORY_SEPARATOR)
    assert len(parts)>1,"%s"%"error parsing %s"%fn
    it = parts[1]
    story = cfg.STORY_SEPARATOR.join(parts[2:-1])
    rt = {'iteration':it,'story':story,'path':fn,'metadata':os.path.join(os.path.dirname(fn),'meta.json'),'id':cfg.STORY_SEPARATOR.join(parts[1:-1])}
    if read:
        root = orgparse.load(fn)
        heading=None
        for node in root[1:]:
            if not heading:
                heading = node.get_heading()
                rt['status']=node.todo
                rt['tags']=node.tags
                rt['summary']=heading
            elif node.get_heading()=='Attributes':
                attrs = parse_attrs(unicode(node))
                for k,v in attrs.items():
                    rt[k]=v
                    if k=='tags':
                        rt[k]=v.split(', ')


    hfn = os.path.join(os.path.dirname(fn),'hours.json')
    if gethours and os.path.exists(hfn):
        hrs = json.loads(open(hfn).read())
        tothrs=0 ; person_hours={} ; last_tracked=None
        for date,data in hrs.items():
            for un,uhrs in data.items():
                if hoursonlyfor and un!=hoursonlyfor: continue
                if un not in person_hours: person_hours[un]={'hours':0,'last_tracked':None}
                curdate = datetime.datetime.strptime(date,'%Y-%m-%d')
                if not last_tracked or last_tracked<curdate:
                    last_tracked = curdate
                if not person_hours[un]['last_tracked'] or person_hours[un]['last_tracked']<curdate:
                    person_hours[un]['last_tracked']=curdate
                tothrs+=uhrs
                person_hours[un]['hours']+=uhrs
        rt['total_hours']=tothrs
        rt['last_tracked']=last_tracked
        person_hours= person_hours.items()
        person_hours.sort(hours_srt_2)
        rt['person_hours']=person_hours



    return rt
taskfiles_cache={}
def get_task_files(iteration=None,assignee=None,status=None,tag=None,recurse=True,recent=False):
    global taskfiles_cache
    tfck = ",".join([str(iteration),str(assignee),str(status),str(tag),str(recurse),str(recent)])
    if tfck in taskfiles_cache: return taskfiles_cache[tfck]

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
    taskfiles_cache[tfck] = files        
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
def hours_srt(s1,s2):
    s1v = s1[1].get('total_hours',0)
    s2v = s2[1].get('total_hours',0)
    if not s1v and not s2v:
        s1v = int(s1[1]['story'].split(cfg.STORY_SEPARATOR)[0])
        s2v = int(s2[1]['story'].split(cfg.STORY_SEPARATOR)[0])
    return cmp(s1v,s2v)
def hours_srt_2(h1,h2):
    return cmp(h1[1]['last_tracked'],h2[1]['last_tracked'])*-1

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
task_cache={}
def get_task(number,read=False,exc=True):
    global task_cache
    tk = '%s-%s-%s'%(number,read,exc)
    if tk in task_cache: 
        return task_cache[tk]
    
    number = str(number)
    tf = [parse_story_fn(fn,read=read) for fn in get_task_files()]
    tasks = dict([(pfn['story'],pfn) for pfn in tf])    
    if exc:
        assert number in tasks,"%s (%s) not in %s"%(number,type(number),'tasks')
    else:
        if number not in tasks: 
            return False
    rt =  tasks[number]
    task_cache[tk]=rt
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
    findcmd = 'find %s -maxdepth %s ! -wholename "*templates*" ! -wholename "*.git*" -type f -iname "%s" %s'%(tpath,md,cfg.TASKFN,add)
    st,op = gso(findcmd) ; assert st==0
    files = [fn for fn in op.split('\n') if fn!='']
    
    tf = [parse_story_fn(fn) for fn in files]
    exstrs = [t['story'] for t in tf if not re.compile('^([\d'+re.escape(cfg.STORY_SEPARATOR)+']+)$').search(t['story'])]
    assert len(exstrs)==0,"%s is not empty"%(exstrs)
    finalnames = [int(t['story'].split(cfg.STORY_SEPARATOR)[-1]) for t in tf]
    if len(finalnames):
        maxid = max(finalnames)
    else:
        maxid=0
    newid = maxid+1
    return str(newid)

def get_participants():
    fn = os.path.join(cfg.DATADIR,'participants.org')
    fp = open(fn,'r') ; gothead=False
    def parseline(ln):
        return [f.strip() for f in ln.split('|') if f.strip()!='']
    rt={}
    while True:
        ln = fp.readline()
        if not ln: break
        if '|' in ln and not gothead:
            headers = parseline(ln)
            gothead=True
            continue
        if ln.startswith('|-'): continue
        row = parseline(ln) 
        row = dict([(headers[i],row[i]) for i in xrange(len(row))])
        #only active ones:
        if row['Active']=='Y':
            rt[row['Username']]=row
    return rt

def add_notification(whom,about,what):
    send_notification(whom,about,what,justverify=True)

    t = get_task(about,read=True)
    if os.path.exists(t['metadata']):
        meta = loadmeta(t['metadata'])
    else:
        meta={}
    meta['notify']={'whom':whom,'about':about,'what':what,'added':datetime.datetime.now().isoformat()}
    savemeta(t['metadata'],meta)

def get_meta_files():
    cmd = 'find %s -name meta.json -type f'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0
    files = [(ln,parse_story_fn(ln)) for ln in op.split('\n') if ln!='']
    return files
    

def process_notifications():
    tfs = get_meta_files()
    files_touched=[]
    for meta,s in tfs:
        m = json.load(open(meta))
        if m.get('notify') and not m['notify']['notified']:
            print 'notification processing %s'%s
            n=m['notify']
            send_notification(n['whom'],n['about'],n['what'])
            m['notify']['notified']=datetime.datetime.now().isoformat()
            fp = open(meta,'w')
            json.dump(m,fp,indent=True)
            fp.close()
            files_touched.append(fp.name)
    if len(files_touched):
        print 'commiting %s touched files.'%(len(files_touched))
        cmd = 'git add '+' '.join(files_touched)+' && git commit -m "automatic commit of updated metafiles." && git push'
        st,op = gso(cmd) ; assert st==0,"%s returned %s:\n%s"%(cmd,st,op)

def send_notification(whom,about,what,justverify=False):
    import sendgrid # we import here because we don't want to force everyone installing this.
    assert cfg.RENDER_URL,"no RENDER_URL specified in config."
    assert cfg.SENDER,"no sender specified in config."

    p = get_participants()
    email = p[whom]['E-Mail']
    t= get_task(about,read=True)
    tpl = what+'_notify'
    tf = tempfile.NamedTemporaryFile(delete=False,suffix='.org')
    if what=='new_story':
        subject = 'New task %s'%t['story']
    else:
        raise Exception('unknown topic %s'%what)
    notify = render(tpl,{'t':t,'url':cfg.RENDER_URL,'recipient':p[whom]},tf.name)
    if justverify:
        return False
    cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(tf.name)
    st,op = gso(cmd) ; assert st==0
    expname = tf.name.replace('.org','.html')
    #print 'written %s'%expname
    assert os.path.exists(expname)
    s = sendgrid.Sendgrid(cfg.SENDGRID_USERNAME,cfg.SENDGRID_PASSWORD,secure=True)
    message = sendgrid.Message(cfg.SENDER,subject,open(tf.name).read(),open(expname).read())
    message.add_to(email,p[whom]['Name'])
    s.web.send(message)
    print 'sent %s to %s'%(subject,email)
    return True

def add_task(iteration=None,parent=None,params={},force_id=None,tags=[]):
    if not iteration: 
        if parent:
            t = get_task(parent)
            iteration = t['iteration']
        else:
            iteration = cfg.BACKLOG
    if iteration=='current':
        iterations = get_iterations()
        current_iteration = get_current_iteration(iterations)
        iteration = current_iteration[1]['name']

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
    pars['status'] = cfg.DEFAULT_STATUS

    for k in ['summary','assignee','points','detail']:
       if k not in pars: pars[k]=None

    if pars['summary'] and type(pars['summary'])==list:
        pars['summary']=' '.join(pars['summary'])


    assert not os.path.exists(newdir),"%s exists"%newdir
    dn = os.path.dirname(newdir)
    assert os.path.exists(dn),"%s does not exist."%dn
    st,op = gso('mkdir -p %s'%newdir) ; assert st==0,"could not mkdir %s"%newdir

    assert not os.path.exists(newtaskfn)
    render('task',params.__dict__,newtaskfn)


    if pars['assignee']:
        taskid = cfg.STORY_SEPARATOR.join([parent,newidx])
        add_notification(whom=pars['assignee'],about=taskid,what='new_story')

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
    for st in rt:
        rt[st].sort(hours_srt,reverse=True)
    return rt
def get_current_iteration(iterations):
    nw = datetime.datetime.now() ; current_iteration=None
    for itp,it in iterations:
        if ('start date' in it and 'end date' in it):
            if (it['start date']<=nw and it['end date']>=nw):
                current_iteration = (itp,it)
    return current_iteration
def makeindex(iteration):

    iterations = get_iterations()
    iterations_stories={}

    #find out the current one
    current_iteration = get_current_iteration(iterations)
    recent = [(tf,parse_story_fn(tf,read=True,gethours=True)) for tf in get_task_files(recent=True)]
    recent.sort(hours_srt,reverse=True)
        
    assignees={}
    #create the dir for shortcuts
    if not os.path.exists(cfg.SDIR): os.mkdir(cfg.SDIR)

    #and render its index in the shortcuts folder
    idxstories = [(fn,parse_story_fn(fn,read=True,gethours=True)) for fn in get_task_files(recurse=True)]
    vardict = {'term':'Index','value':'','stories':by_status(idxstories),'relpath':True,'statuses':cfg.STATUSES,'iteration':False}
    render('tasks',vardict,os.path.join(cfg.SDIR,'index.org'))

    for it in iterations:
        #print 'cycling through iteration %s'%it[0]
        if iteration and str(it[1]['name'])!=str(iteration): 
            #print 'skipping iteration %s'%(it[0])
            continue
        #print 'walking iteration %s'%it[0]
        taskfiles = get_task_files(iteration=it[1]['name'],recurse=True)
        stories = [(fn,parse_story_fn(fn,read=True,gethours=True)) for fn in taskfiles]
        stories.sort(taskid_srt,reverse=True)        

        #let's create symlinks for all those stories to the root folder.
        for tl in stories:
            tpath = tl[0]
            taskid = '-'.join(tl[1]['story'].split(cfg.STORY_SEPARATOR))
            spath = os.path.join(cfg.SDIR,taskid)
            dpath = '/'+tl[1]['iteration']+'/'+tl[1]['story']
            ldest = os.path.join('..',os.path.dirname(tpath))
            cmd = 'ln -s %s %s'%(ldest,spath)
            needrun=False
            if os.path.islink(spath):
                ls = os.readlink(spath)
                #print 'comparing %s <=> %s'%(ls,ldest)
                if ls!=ldest:
                    os.unlink(spath)
                    needrun=True
                    #print 'needrun because neq'
            else:
                needrun=True
                #print 'needrunq because nex %s'%(spath)
            if needrun:
                st,op = gso(cmd) ; assert st==0,"%s returned %s"%(cmd,st)

        shallowstories = [st for st in stories if len(st[1]['story'].split(cfg.STORY_SEPARATOR))==1]
        iterations_stories[it[1]['name']]=len(shallowstories)

        vardict = {'term':'Iteration','value':it[1]['name'],'stories':by_status(shallowstories),'relpath':True,'statuses':cfg.STATUSES,'iteration':False} #the index is generated only for the immediate 1-level down stories.
        itidxfn = os.path.join(cfg.DATADIR,it[0],'index.org')
        fp = open(itidxfn,'w') ; fp.write(open(os.path.join(cfg.DATADIR,it[0],'iteration.org')).read()) ; fp.close()
        stlist = render('tasks',vardict,itidxfn,'a') 

        #we show an iteration index of the immediate 1 level down tasks

        for st in stories:
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

            pars = {'children':ch,'story':st[1],'TASKFN':cfg.TASKFN,'GITWEB_URL':cfg.GITWEB_URL,'pgd':parsegitdate}
            if os.path.exists(pars['story']['metadata']):
                pars['meta']=loadmeta(pars['story']['metadata'])
            else:
                pars['meta']=None
            
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
            stories = [(fn,parse_story_fn(fn,read=True,gethours=True,hoursonlyfor=assignee)) for fn in tf]
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

    cfn = os.path.join(cfg.DATADIR,'changes.org')
    render('changes',{'changes':get_changes(),'pfn':parse_story_fn},cfn)

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

def get_changes(show=False):
    st,op = gso('git log --pretty=oneline -30') ; assert st==0
    commits = dict([(c.split(' ')[0],{'message':' '.join(c.split(' ')[1:])}) for c in op.split('\n') if c!=''])
    for cid,cmsg in commits.items():
        cmd = "git show %s | egrep '^Date:'"%cid
        st,op = gso(cmd)
        dt = op.replace('Date:','').strip('\n \t')
        commits[cid]['date']=dt
        cmd = "git show %s | egrep '^(\-\-\-|\+\+\+)' | egrep -v 'dev/null' | egrep  'task.org$'"%(cid)
        st,op = gso(cmd) ; assert st in [0,256],"%s => %s\n%s"%(cmd,st,op)
        lines = [l for l in op.split('\n') if l!='']
        ulines=[]
        for l in lines:
            for r in ['--- a/','+++ a/','--- b/','+++ b/']: l=l.replace(r,'')
            if l not in ulines: 
                ulines.append(l)
                #pt.add_row([dt,cid,cmsg['message'],l,parse_story_fn(l)['id']])
        commits[cid]['changes']=ulines
    if show:
        pt = PrettyTable(['date','commit','message','file','story'])
        for cid,cdata in commits.items():
            for cfn in cdata['changes']:
                pt.add_row([cdata['date'],cid,cdata['message'],cfn,parse_story_fn(cfn)['id']])
        print pt
    return commits

commitre = re.compile('\[origin\/([^\]]+)\]')
cre = re.compile('commit ([0-9a-f]{40})')
are = re.compile('Author: ([^<]*) <([^>]+)>')
sre = re.compile('#([0-9'+re.escape(cfg.STORY_SEPARATOR)+']+)')
dre = re.compile('Date:   (.*)')

def imp_commits(args):
    if not os.path.exists(cfg.REPO_DIR): os.mkdir(cfg.REPO_DIR)
    excommits = loadcommits()
    for repo in cfg.REPOSITORIES:
        print 'running repo %s'%repo
        repon = os.path.basename(repo).replace('.git','')
        repodir = os.path.join(cfg.REPO_DIR,os.path.basename(repo))
        if not os.path.exists(repodir):
            print 'cloning.'
            cmd = 'git clone %s %s'%(repo,repodir)
            st,op = gso(cmd) ; assert st==0
        prevdir = os.getcwd()
        os.chdir(repodir)
        #refresh the repo
        
        if not args.nofetch:
            print 'fetching.'
            st,op = gso('git fetch -a') ; assert st==0

        print 'running show-branch'
        cmd = 'git show-branch -r'
        st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)
        commits=[] ; ignoredbranches=[]
        for ln in op.split('\n'):
            if ln=='': continue
            if ln.startswith('warning:'): 
                if 'ignoring' not in ln:
                    print ln
                else:
                    ign = re.compile('origin/([^;]+)').search(ln).group(1)
                    ignoredbranches.append(ign)
                continue
            if ln.startswith('------'): continue
            res = commitre.search(ln)
            if res:
                exact = res.group(1) ; branch = exact
                #strip git niceness to get branch name
                for sym in ['~','^']:branch = branch.split(sym)[0]
                commits.append([exact,branch,False])
            else:
                if not re.compile('^(\-+)$').search(ln):
                    print 'cannot extract',ln
        #now go over the ignored branches
        if len(ignoredbranches): 
            for ign in set(ignoredbranches):
                st,op = gso('git checkout origin/%s'%(ign)); assert st==0
                st,op = gso('git log --pretty=oneline --since=%s'%(datetime.datetime.now()-datetime.timedelta(days=10)).strftime('%Y-%m-%d')) ; assert st==0
                for lln in op.split('\n'):
                    if lln=='': continue
                    lcid = lln.split(' ')[0]
                    commits.append([lcid,ign,True])
                    #print 'added ign %s / %s'%(lcid,ign)

        cnt=0 ; branches=[]
        print 'going over %s commits.'%len(commits)
        for relid,branch,isexact in commits:
            if isexact:
                cmd = 'git show %s | head'%relid
            else:
                cmd = 'git show origin/%s | head'%relid
            st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)
            if op.startswith('fatal'):
                raise Exception('%s returned %s'%(cmd,op))
            cres = cre.search(op)
            dres = dre.search(op)
            if not dres: raise Exception(op)
            dt = dres.groups()[0]
            cid = cres.group(1)
            author,email = are.search(op).groups()
            un = cfg.COMMITERMAP(email,author)
            storyres = sre.search(op)
            if storyres:
                task = storyres.group(1)
            else:
                task = None
            cinfo = {'s':dt,'br':branch,'u':un,'t':task} #'repo':repon, 'cid':cid <-- these are out to save space
            if branch not in branches: branches.append(branch)
            key = '%s/%s'%(repon,cid)
            excommits[key]=cinfo
            cnt+=1
            #print '%s: %s/%s %s by %s on task %s'%(dt,repon,branch,cid,un,task)
        print 'found out about %s commits, branches %s'%(cnt ,branches)
        os.chdir(prevdir)        
        fp = open(commitsfn,'w')
        json.dump(excommits,fp,indent=True,sort_keys=True) ; fp.close()
def loadmeta(fn):
    if os.path.exists(fn):
        return json.load(open(fn))
    else:
        return {}
def savemeta(fn,dt):
    fp = open(fn,'w')
    json.dump(dt,fp,sort_keys=True,indent=True)
    fp.close()

numonths = 'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'.split('|')
redt = re.compile('^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) ('+'|'.join(numonths)+') ([0-9]{1,2}) ([0-9]{2})\:([0-9]{2})\:([0-9]{2}) ([0-9]{4}) (\-|\+)([0-9]{4})')
def parsegitdate(s):
    dtres = redt.search(s)
    wd,mon,dy,hh,mm,ss,yy,tzsign,tzh = dtres.groups()
    dt = datetime.datetime(year=int(yy),
                           month=int(numonths.index(mon)+1),
                           day=int(dy),
                           hour=int(hh),
                           minute=int(mm),
                           second=int(ss))
    return dt

def assign_commits():
    exc = json.load(open(commitsfn,'r'))
    metas={}
    print 'going over commits.'
    for ck,ci in exc.items():
        if not ci['t']: continue
        repo,cid = ck.split('/')
        t = get_task(ci['t'],exc=False)
        if not t: 
            print 'could not find task %s'%(ci['t'])
            continue

        #metadata cache
        if t['metadata'] not in metas: 
            m = loadmeta(t['metadata'])
            metas[t['metadata']]=m
            m['commits_qty']=0 #we zero it once upon load to be incremented subsequently
        else: m = metas[t['metadata']]

        m['commits_qty']+=1

        repocommiter = '-'.join([repo,ci['u']])
        if 'commiters' not in m: m['commiters']=[]
        if repocommiter not in m['commiters']: m['commiters'].append(repocommiter)
        
        repobranch = '/'.join([repo,ci['br']])
        if 'branches' not in m: m['branches']=[]
        if repobranch not in m['branches']: m['branches'].append(repobranch)

        dt = parsegitdate(ci['s'])

        lastdatekey = '%s-%s'%(repo,ci['u'])
        if 'lastcommits' not in m: m['lastcommits']={}
        if lastdatekey not in m['lastcommits'] or parsegitdate(m['lastcommits'][lastdatekey])<dt:
            m['lastcommits'][lastdatekey]=ci['s']

        lastbranchkey = '%s/%s'%(repo,ci['br'])
        if 'branchlastcommits' not in m: m['branchlastcommits']={}
        if lastbranchkey not in m['branchlastcommits'] or parsegitdate(m['branchlastcommits'][lastbranchkey])<dt:
            m['branchlastcommits'][lastbranchkey]=ci['s']

    print 'saving.'
    for fn,m in metas.items():
        savemeta(fn,m)
    print '%s metas touched.'%(len(metas))


        
    
    
if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Task Control',prog='tasks.py')
    subparsers = parser.add_subparsers(dest='command')

    lst = subparsers.add_parser('list')
    lst.add_argument('--iteration',dest='iteration')
    lst.add_argument('--assignee',dest='assignee')
    lst.add_argument('--status',dest='status')
    lst.add_argument('--tag',dest='tag')
    lst.add_argument('--recent',dest='recent',action='store_true')

    gen = subparsers.add_parser('index')
    gen.add_argument('--iteration',dest='iteration')

    html = subparsers.add_parser('makehtml')
    html.add_argument('--iteration',dest='iteration')
    html.add_argument('--notasks',dest='notasks',action='store_true')
    html.add_argument('files',nargs='*')

    nw = subparsers.add_parser('new')
    nw.add_argument('--iteration',dest='iteration')
    nw.add_argument('--parent',dest='parent')
    nw.add_argument('--assignee',dest='assignee')
    nw.add_argument('--id',dest='id')
    nw.add_argument('--tag',dest='tags',action='append')
    nw.add_argument('summary',nargs='+')

    purge = subparsers.add_parser('purge')
    purge.add_argument('tasks',nargs='+')
    purge.add_argument('--force',dest='force',action='store_true')

    show = subparsers.add_parser('show')
    show.add_argument('tasks',nargs='+')

    move = subparsers.add_parser('move')
    move.add_argument('fromto',nargs='+')

    odi = subparsers.add_parser('odesk_import')
    odi.add_argument('--from',dest='from_date')
    odi.add_argument('--to',dest='to_date')

    ed = subparsers.add_parser('edit')
    ed.add_argument('tasks',nargs='+')
    
    pr = subparsers.add_parser('process_notifications')
    ch = subparsers.add_parser('changes')

    git = subparsers.add_parser('fetch_commits')
    git.add_argument('--nofetch',dest='nofetch',action='store_true')
    git.add_argument('--import',dest='imp',action='store_true')
    git.add_argument('--assign',dest='assign',action='store_true')

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
    if args.command=='odesk_import':
        from commits import odesk_fetch
        if not args.from_date: args.from_date=(datetime.datetime.now()-datetime.timedelta(days=1)) #.strftime('%Y-%m-%d')
        else: args.from_date = datetime.datetime.strptime(args.from_date,'%Y-%m-%d')
        if not args.to_date: args.to_date=(datetime.datetime.now()-datetime.timedelta(days=1)) #.strftime('%Y-%m-%d')
        else: args.to_date = datetime.datetime.strptime(args.to_date,'%Y-%m-%d')
        
        i = args.from_date
        while i.date()<=args.to_date.date():
            print i
            rt = odesk_fetch.run_query(date_from=i.strftime('%Y-%m-%d'),date_to=i.strftime('%Y-%m-%d'))
            rel = rt['by_story_provider']
            out = {}
            for sid,dt in rel.items():
                if sid=='None': continue
                out[sid]={} ; nasgn={}
                for un,hrs in dt.items(): nasgn[cfg.USERMAP(un)]=hrs
                out[sid]=nasgn
                try:
                    t = get_task(sid)
                except:
                    print 'could not find task %s: %s'%(sid,dt)
                    continue
                ofn = os.path.join(os.path.dirname(t['path']),'hours.json')
                if not os.path.exists(ofn):
                    hours = {}
                else:
                    hours = json.loads(open(ofn).read())
                ts = '%s'%(i.strftime('%Y-%m-%d'))
                hours[ts]=nasgn
                fp = open(ofn,'w') ; fp.write(json.dumps(hours,indent=True,sort_keys=True)) ; fp.close()
                print 'written %s in %s'%(ts,ofn)
            i+=datetime.timedelta(days=1)
    if args.command=='edit':
        tfiles = [get_task(t)['path'] for t in args.tasks]
        cmd = 'emacs '+' '.join(tfiles)
        st,op=gso(cmd)
    if args.command=='process_notifications':
        process_notifications()
    if args.command=='changes':
        get_changes(show=True)
    if args.command=='fetch_commits':
        if args.imp:
            imp_commits(args)
        if args.assign:
            assign_commits()
