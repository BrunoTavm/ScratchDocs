#!/usr/bin/env python
import argparse

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


def load_templates():
    if not os.path.exists(cfg.MAKO_DIR): os.mkdir(cfg.MAKO_DIR)
    _prefix = os.path.dirname(__file__)
    if cfg.TPLDIR:
        tpldir = cfg.TPLDIR
    else:
        tpldir = os.path.join(_prefix,'templates')
    lk = TemplateLookup(directories=['.'])
    rt = {}
    rt['task'] = Template(filename=(os.path.join(tpldir,'task.org')),lookup = lk,module_directory=cfg.MAKO_DIR)
    rt['iterations'] = Template(filename=os.path.join(tpldir,'iterations.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
    rt['tasks'] = Template(filename=os.path.join(tpldir,'tasks.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
    rt['taskindex'] = Template(filename=os.path.join(tpldir,'taskindex.org'),lookup = lk,module_directory=cfg.MAKO_DIR)            
    rt['iteration'] = Template(filename=os.path.join(tpldir,'iteration.org'),lookup = lk,module_directory=cfg.MAKO_DIR)            
    rt['new_story_notify'] = Template(filename=os.path.join(tpldir,'new_story_notify.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
    rt['change_notify'] = Template(filename=os.path.join(tpldir,'change_notify.org'),lookup = lk,module_directory=cfg.MAKO_DIR)
    rt['changes'] = Template(filename=os.path.join(tpldir,'changes.org'),lookup = lk,module_directory=cfg.MAKO_DIR)     
    rt['demo'] = Template(filename=os.path.join(tpldir,'demo.org'),lookup = lk,module_directory=cfg.MAKO_DIR)     
    return rt

ckre = re.compile('^'+re.escape('<!-- checksum:')+'([\d\w]{32})'+re.escape(' -->'))
def md5(fn):
    st,op = gso('md5sum %s'%fn); assert st==0
    op = op.split(' ')
    return op[0]

def loadcommits():
    global commits
    if not len(commits):
        if not os.path.exists(commitsfn):
            commits={}
        else:
            commits = json.load(open(commitsfn,'r'))
    return commits

tpls={}
def render(tplname,params,outfile=None,mode='w'):
    """helper to renders one of the mako templates defined above"""
    global tpls
    if not len(tpls):
        tpls = load_templates()

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
    return r

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
tokre = re.compile('^\- ([^\:]+)')
stokre = re.compile('^  \- (.+)')
def parse_attrs(node,pth):
    try:
        rt= dict([a[2:].split(' :: ') for a in node.split('\n') if a.startswith('- ') and ' :: ' in a])
        tokagg={}

        intok=False
        for ln in node.split('\n'):
            tokres = tokre.search(ln)
            if not tokres: 
                if intok:
                    stok = stokre.search(ln)
                    if stok:
                        stok = stok.group(1)
                        res = linkre.search(stok)
                        if res:
                            url,anchor = res.groups()
                            tokagg[tok].append({'url':url,'anchor':anchor})
                        else:
                            tokagg[tok].append(stok)
                    else:
                        raise Exception('wtf is %s (under %s) parsing %s'%(ln,tok,pth))
            else:
                tok = tokres.group(1)
                tokagg[tok]=[]
                if tok in ['informed','links','repobranch']:
                    intok=True
    except:
        print node.split('\n')
        raise
    for k,v in rt.items():
        if k.endswith('date'):
            rt[k]=datetime.datetime.strptime(v.strip('<>[]'),'%Y-%m-%d')
        if k in ['created at']:
            dt = v.strip('<>[]').split('.')
            rt[k]=datetime.datetime.strptime(dt[0],'%Y-%m-%d %H:%M:%S')
            if len(dt)>1:
                rt[k]+=datetime.timedelta(microseconds=int(dt[1]))

    for ta,tv in tokagg.items():
        rt[ta]=tv

    #if '338/task.org' in pth:print json.dumps(rt,indent=True,default=lambda x: str(x)) ; raise Exception('here it is %s'%pth)
    return rt
UNSSEP = '# UNSTRUCTURED BEYOND THIS POINT'
def parse_story_fn(fn,read=False,gethours=False,hoursonlyfor=None,getmeta=True):
    """parse a task filename and optionally read it."""
    assert len(fn)
    parts = [prt for prt in fn.replace(cfg.DATADIR,'').split(cfg.STORY_SEPARATOR) if prt!='']
    assert len(parts)>1,"%s"%"error parsing %s"%fn
    it = parts[0]
    story = cfg.STORY_SEPARATOR.join(parts[1:-1])
    rt = {'iteration':it,'story':story,'path':fn,'metadata':os.path.join(os.path.dirname(fn),'meta.json'),'id':cfg.STORY_SEPARATOR.join(parts[1:-1])}
    #raise Exception('id for %s is %s from %s'%(fn,rt['id'],parts))
    if read:
        filecont = open(fn,'r').read()
        root = orgparse.load(fn)
        heading=None
        gotattrs=False ; unstructured=''
        for node in root[1:]:
            if not heading:
                heading = node.get_heading()
                rt['status']=node.todo
                rt['tags']=node.tags
                rt['summary']=heading
            elif node.get_heading()=='Attributes':
                attrs = parse_attrs(unicode(node),fn)
                for k,v in attrs.items():
                    rt[k]=v
                    if k=='tags':
                        rt[k]=v.split(', ')
                gotattrs=True
            elif gotattrs and UNSSEP not in filecont:
                unstructured+=str(node)+'\n'

        if UNSSEP in filecont:
            assert not len(unstructured)
            unstructured = filecont.split(UNSSEP)[1]

        rt['unstructured']=unstructured

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
    mfn = os.path.join(os.path.dirname(fn),'meta.json')
    if getmeta:
        rt['meta']=loadmeta(mfn)

    return rt
taskfiles_cache={}
def flush_taskfiles_cache():
    global taskfiles_cache
    taskfiles_cache={}

def get_task_files(iteration=None,assignee=None,status=None,tag=None,recurse=True,recent=False,flush=False):
    """return task filenames according to provided criteria"""
    global taskfiles_cache
    tfck = ",".join([str(iteration),str(assignee),str(status),str(tag),str(recurse),str(recent)])
    if flush: flush_taskfiles_cache()
    if tfck in taskfiles_cache: return taskfiles_cache[tfck]

    if iteration:
        if iteration.startswith('not '):
            pf='!'
            itval = iteration.replace('not ','')
        else:
            pf=''
            itval=iteration
        itcnd='%s -wholename "%s/*"'%(pf,os.path.join(cfg.DATADIR,str(itval)))
    else:
        itcnd=''
    if not recurse:
        add=' -maxdepth 3'
    else:
        add=''
    cmdtpl = "find  %s  %s ! -wholename '*templates*' ! -wholename '*.git*' %s -type f -name '%s'"
    if iteration:
        itdir = os.path.join(cfg.DATADIR,iteration)
        st,op  = gso('find %s -maxdepth 1 -type l '%(itdir)) ; assert st==0
        itdirs = [itdir]+[ldir+'/' for ldir in op.split('\n') if op!='']
        cmds = [cmdtpl%(dr,add,itcnd,cfg.TASKFN) for dr in itdirs]
    else:
        cmds = [cmdtpl%(cfg.DATADIR,add,itcnd,cfg.TASKFN)]
    files=[]
    for cmd in cmds:
        #print cmd
        st,op = gso(cmd) ;assert st==0,"%s => %s"%(cmd,op)
        files += [fn for fn in op.split('\n') if fn!='']
    files=list(set(files))

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
            if status and status.startswith('not ') and status.replace('not ','')!=s['status']:
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

def get_parent(tid,tl=False):
    spl = tid.split('/')
    if len(spl)>1:
        if tl:
            return spl[0]
        else:
            return spl[-2]
    else:
        return spl[0]

numre = re.compile('^\d+$')
def iteration_srt(s1,s2):
    i1 = s1['iteration']
    i2 = s2['iteration']
    if numre.search(i1) and numre.search(i2):
        rt= cmp(int(i1),int(i2))*-1
    elif numre.search(i1):
        rt= 1
    elif numre.search(i2):
        rt= -1
    else:
        rt= cmp(i1,i2)
    if rt==0:
        parts1 = s1['story'].split(cfg.STORY_SEPARATOR)
        parts2 = s2['story'].split(cfg.STORY_SEPARATOR)
        p1='' ; p2=''
        while p1==p2:
            if len(parts1):
                p1 = parts1.pop(0)
            else:
                p1='0'
            if len(parts2):
                p2 = parts2.pop(0)
            else:
                p2='0'
        rt = cmp(int(p1),int(p2))
        #rt = cmp(int(s1['story'].split(cfg.STORY_SEPARATOR)[0]),int(s2['story'].split(cfg.STORY_SEPARATOR)[0]))*-1
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
            attrs = parse_attrs(unicode(node),pth)
            for k,v in attrs.items(): rt[k]=v
    return rt
def get_iterations():
    cmd = 'find  %s -maxdepth 2 -name "iteration.org" ! -wholename "*templates*" ! -wholename "*repos/*" -type f'%(cfg.DATADIR)
    #cmd = 'find %s -maxdepth 1 ! -wholename "*.git*"  -type d'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0
    #print op  ; raise Exception('w00t')
    dirs = op.split('\n')
    rt = [(os.path.dirname(path),parse_iteration(path)) for path in dirs if len(path.split('/'))>1]
    rt.sort(sort_iterations,reverse=True)
    return rt
task_cache={}
def get_task(number,read=False,exc=True,flush=False,gethours=False):
    """return everything we know about a task"""
    global task_cache
    tk = '%s-%s-%s'%(number,read,exc)
    if tk in task_cache: 
        if flush: del task_cache[tk]
        else: return task_cache[tk]
    
    number = str(number)
    tf = [parse_story_fn(fn,read=read,gethours=gethours) for fn in get_task_files(recurse=True,flush=flush)]

    tasks = dict([(pfn['story'],pfn) for pfn in tf])    

    if exc:
        assert number in tasks,"%s (%s) not in %s"%(number,type(number),tasks.keys()) #'tasks')
    else:
        if number not in tasks: 
            return False
    rt =  tasks[number]
    task_cache[tk]=rt
    return rt

def get_children(number):
    t = get_task(number)
    cmd = 'find -L %s -maxdepth 2 ! -wholename "*.git*" -type f -iname "%s" ! -wholename "%s"'%(os.path.dirname(t['path']),cfg.TASKFN,t['path'])
    st,op = gso(cmd) ; assert st==0,"%s returned %s:\n%s"%(cmd,st,op)
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

def get_table_contents(fn):
    ffn = os.path.join(cfg.DATADIR,fn)
    fp = open(ffn,'r') ; gothead=False
    def parseline(ln):
        return [f.strip() for f in ln.split('|') if f.strip()!='']
    rt=[]
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
        rt.append(row)
        #only active ones:
    return rt

def get_participants(disabled=False):
    tconts = get_table_contents('participants.org')
    rt={}
    for row in tconts:
        if disabled or row['Active']=='Y':
            rt[row['Username']]=row
    return rt

def get_story_trans():
    tconts = get_table_contents('taskmap.org')
    rt = {}
    for t in tconts:
        rt[t['Task']]=t['Target']
    return rt
    #raise Exception(tconts)

def add_notification(whom,about,what):
    send_notification(whom,about,what,how=None,justverify=True)

    t = get_task(about,read=True)
    if os.path.exists(t['metadata']):
        meta = loadmeta(t['metadata'])
    else:
        meta={}
    if 'notifications' not in meta: meta['notifications']=[]
    meta['notifications'].append({'whom':whom,'about':about,'what':what,'added':datetime.datetime.now().isoformat()})
    savemeta(t['metadata'],meta)

def get_meta_files():
    cmd = 'find %s -name meta.json -type f'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0
    files = [(ln,parse_story_fn(ln)) for ln in op.split('\n') if ln!='']
    return files
    

def process_notifications(args):
    tfs = get_meta_files()
    files_touched=[]
    participants = get_participants(disabled=True)

    for meta,s in tfs:
        m = loadmeta(meta)
        if m.get('notifications'):
            for n in m['notifications']:
                if n.get('notified'): continue
                #print 'notification processing %s'%s
                whom = participants[n['whom']]
                if whom['E-Mail']!=n['author_email'] and whom['Active']=='Y':
                    send_notification(n['whom'],n['about'],n['what'],n.get('how'),body=n)
                else:
                    print 'silencing notify about a commit by %s to %s'%(n['author'],n['whom'])
                n['notified']=datetime.datetime.now().isoformat()
                savemeta(meta,m)
                files_touched.append(meta)
    if len(files_touched) and not args.nocommit:
        print 'commiting %s touched files.'%(len(files_touched))
        cmd = 'git add '+' '.join(files_touched)+' && git commit -m "automatic commit of updated metafiles." && git push'
        st,op = gso(cmd) ; assert st==0,"%s returned %s:\n%s"%(cmd,st,op)

def send_notification(whom,about,what,how=None,justverify=False,body={}):
    import sendgrid # we import here because we don't want to force everyone installing this.
    assert cfg.RENDER_URL,"no RENDER_URL specified in config."
    assert cfg.SENDER,"no sender specified in config."

    p = get_participants()
    try:
        email = p[whom]['E-Mail']
    except KeyError:
        print '%s not in %s'%(whom,p.keys())
        return False
    t= get_task(about,read=True)
    tpl = what+'_notify'
    tf = tempfile.NamedTemporaryFile(delete=False,suffix='.org')
    if what=='new_story':
        subject = 'New task %s'%t['story']
        rdt = {'t':t,'url':cfg.RENDER_URL,'recipient':p[whom]}
    elif what=='change':
        subject = '%s changed by %s'%(t['story'],body['author_name'])
        assert cfg.GITWEB_URL
        assert cfg.DOCS_REPONAME
        rdt = {'t':t,'url':cfg.RENDER_URL,'recipient':p[whom],'commit':how,'gitweb':cfg.GITWEB_URL,'docsrepo':cfg.DOCS_REPONAME,'body':body}
    else:
        raise Exception('unknown topic %s'%what)
    notify = render(tpl,rdt,tf.name)
    #print open(tf.name,'r').read() ; raise Exception('bye')
    if justverify:
        return False
    cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(tf.name)
    st,op = gso(cmd) ; assert st==0
    expname = tf.name.replace('.org','.html')
    #print 'written %s'%expname
    assert os.path.exists(expname)
    s = sendgrid.Sendgrid(cfg.SENDGRID_USERNAME,cfg.SENDGRID_PASSWORD,secure=True)
    if body and body.get('authormail'):
        sender = body.get('authormail')
    else:
        sender = cfg.SENDER

    message = sendgrid.Message(sender,subject,open(tf.name).read(),open(expname).read())
    message.add_to(email,p[whom]['Name'])
    s.web.send(message)
    print 'sent %s to %s'%(subject,email)
    return True
def add_iteration(name,start_date=None,end_date=None):
    itdir = os.path.join(cfg.DATADIR,name)
    itfn = os.path.join(itdir,'iteration.org')
    assert not os.path.exists(itdir),"%s exists."%itdir
    os.mkdir(itdir)
    render('iteration',{'start_date':start_date,'end_date':end_date},itfn)

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
        tf = [parse_story_fn(fn) for fn in get_task_files(iteration=iteration,flush=True)]
        iterationtasks = dict([(tpfn['story'],tpfn) for tpfn in tf])
        assert parent in iterationtasks,"%s not in %s"%(parent,iterationtasks)
        basedir = os.path.dirname(iterationtasks[parent]['path'])
        if force_id:
            newidx = force_id
        else:
            newidx = get_new_idx(parent=parent)
        newdir = os.path.join(basedir,newidx)
        fullid = cfg.STORY_SEPARATOR.join([parent,newidx])
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
        fullid = cfg.STORY_SEPARATOR.join([newidx])
        newtaskfn = os.path.join(newdir,'task.org')
    newtaskdt = parse_story_fn(newtaskfn)
    assert newtaskdt
    print 'creating new task %s : %s'%(newtaskdt['story'],pfn(newtaskfn))
    if type(params)==dict:
        pars = dict(params)
    else:
        pars = params.__dict__
    pars['story_id'] = newidx
    pars['created'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if 'creator' not in pars:
        pars['creator'] = cfg.CREATOR
    if 'status' not in pars:
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
    pars['tags']=tags
    render('task',pars,newtaskfn)
    pars['path']=newtaskfn
    #clear the cache for tasks
    global task_cache,taskfiles_cache
    task_cache={}
    taskfiles_cache={}

    # change notifications will suffice for now
    # if pars['assignee']:
    #     if parent:
    #         jn = [parent,newidx]
    #     else:
    #         jn = [newidx]
    #     taskid = cfg.STORY_SEPARATOR.join(jn)
    #     add_notification(whom=pars['assignee'],about=taskid,what='new_story')
    pars['id']=fullid
    return pars

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
            if (it['start date'].date()<=nw.date() and it['end date'].date()>=nw.date()):
                current_iteration = (itp,it)
    assert current_iteration,"no current iteration"
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
    vardict = {'term':'Index','value':'','stories':by_status(idxstories),'relpath':True,'statuses':cfg.STATUSES,'iteration':False,'statusagg':{}}
    routfile= os.path.join(cfg.SDIR,'index.org')
    #print 'rendering %s'%routfile
    render('tasks',vardict,routfile)

    for it in iterations:
        #print 'cycling through iteration %s'%it[0]
        if iteration and str(it[1]['name'])!=str(iteration): 
            #print 'skipping iteration %s'%(it[0])
            continue
        #print 'walking iteration %s'%it[0]
        taskfiles = get_task_files(iteration=it[1]['name'],recurse=True)
        stories = [(fn,parse_story_fn(fn,read=True,gethours=True)) for fn in taskfiles]
        stories_by_id = dict([(st[1]['id'],st[1]) for st in stories])
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

        #aggregate subtask statuses
        statusagg = {}
        for st in stories:
            #calcualte children
            chids = ([sst[1]['id'] for sst in stories if sst[1]['id'].startswith(st[1]['id']) and len(sst[1]['id'])>len(st[1]['id'])])
            if len(chids):
                statuses = {}
                for chid in chids:
                    sti = stories_by_id[chid]
                    if sti['status'] not in statuses: statuses[sti['status']]=0
                    statuses[sti['status']]+=1
                statusagg[st[1]['id']]=statuses

        vardict = {'term':'Iteration','value':it[1]['name'],'stories':by_status(shallowstories),'relpath':True,'statuses':cfg.STATUSES,'iteration':False,'statusagg':statusagg} #the index is generated only for the immediate 1-level down stories.
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

            pars = {'children':ch,'story':st[1],'TASKFN':cfg.TASKFN,'GITWEB_URL':cfg.GITWEB_URL,'pgd':parsegitdate,'RENDER_URL':cfg.RENDER_URL}
            if os.path.exists(pars['story']['metadata']):
                pars['meta']=loadmeta(pars['story']['metadata'])
            else:
                pars['meta']=None
            
            render('taskindex',pars,storyidxfn,'w')
            fp = open(storyidxfn,'a') ; fp.write(open(st[1]['path']).read()) ; fp.close()

            #print idxcont
    participants = get_participants()

    assigned_files={} ; excl=[]
    for asfn in ['alltime','current']:
        for assignee,storycnt in assignees.items():
            if assignee!=None and assignee not in participants:
                if assignee not in excl:
                    #print 'excluding %s'%assignee
                    excl.append(assignee)
                continue
            afn = 'assigned-'+assignee+'-'+asfn+'.org'
            ofn = os.path.join(cfg.DATADIR,afn)
            if assignee not in assigned_files: assigned_files[assignee]={}
            
            assigned_files[assignee][asfn]=afn
            if asfn=='current' and current_iteration:
                f_iter = current_iteration[1]['name']
                assert f_iter
            else:
                f_iter=None

            tf = get_task_files(assignee=assignee,recurse=True,iteration=f_iter)
            stories = [(fn,parse_story_fn(fn,read=True,gethours=True,hoursonlyfor=assignee)) for fn in tf]
            stories.sort(status_srt)
            vardict = {'term':'Assignee','value':'%s (%s)'%(assignee,storycnt),'stories':by_status(stories),'relpath':False,'statuses':cfg.STATUSES,'iteration':True,'statusagg':{}}
            cont = render('tasks',vardict,ofn)


    vardict = {'iterations':iterations,
               'iterations_stories':iterations_stories,
               'assigned_files':assigned_files,
               'assignees':assignees,
               'current_iteration':current_iteration,
               'recent_tasks':recent,
               'statusagg':{}
               }
    idxfn = os.path.join(cfg.DATADIR,'index.org')
    itlist = render('iterations',vardict,idxfn)

    cfn = os.path.join(cfg.DATADIR,'changes.org')
    render('changes',{'GITWEB_URL':cfg.GITWEB_URL,'DOCS_REPONAME':cfg.DOCS_REPONAME,'changes':get_changes(),'pfn':parse_story_fn},cfn)

def list_stories(iteration=None,assignee=None,status=None,tag=None,recent=False):
    files = get_task_files(iteration=iteration,assignee=assignee,status=status,tag=tag,recent=recent)
    pt = PrettyTable(['iteration','id','summary','assigned to','status','tags'])
    pt.align['summary']='l'
    cnt=0
    for fn in files:
        sd = parse_story_fn(fn,read=True)
        if iteration and iteration.startswith('not ') and sd['iteration']==iteration.replace('not ',''): 
            continue
        elif iteration and not iteration.startswith('not ') and sd['iteration']!=str(iteration): continue
        if len(sd['summary'])>60: summary=sd['summary'][0:60]+'..'
        else: summary = sd['summary']
        pt.add_row([sd['iteration'],sd['story'],summary,sd['assigned to'],sd['status'],','.join(sd.get('tags',''))])
        cnt+=1
    pt.sortby = 'status'
    print pt
    print '%s stories.'%cnt

def get_changes(show=False,add_notifications=False):
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
    pt = PrettyTable(['date','commit','message','file','story'])
    notifyover={}
    for cid,cdata in commits.items():
        #print 'going over commit %s which has %s changes'%(cid,len(cdata['changes']))
        for cfn in cdata['changes']:
            if os.path.exists(cfn):
                pfn = parse_story_fn(cfn,read=True)
                sid = pfn['id']
            else:
                pfn = None
                sid = None
            pt.add_row([cdata['date'],cid,cdata['message'],cfn,sid])

            if '@DONTNOTIFY' not in cdata['message'] and add_notifications and pfn:
                for fn in ['created by','assigned to','informed']:
                    if not pfn.get(fn) or pfn.get('fn')=='None':
                        continue
                    if fn=='informed':
                        whoms = pfn.get(fn)
                    else:
                        whoms = [pfn.get(fn)]
                    for whom in whoms:
                        if not whom or whom=="None": continue
                        if sid not in notifyover:
                            notifyover[sid]={}
                        if whom not in notifyover[sid]:
                            notifyover[sid][whom]=[]
                        if cid not in  notifyover[sid][whom]:
                            notifyover[sid][whom].append(cid)

    metas={}
    for sid,people in notifyover.items():
        for person,commits in people.items():
            for cid in commits:
                if not sid: continue
                s = get_task(sid)
                if s['metadata'] in metas:
                    m = metas[s['metadata']]
                else:
                    m = loadmeta(s['metadata'])
                if 'notifications' not in m: m['notifications']=[]
                toks = ['%s-%s'%(n['whom'],n.get('how')) for n in m['notifications']]
                mytok = '%s-%s'%(person,cid)
                if mytok in toks: continue
                #{u'notified': u'2012-11-13T13:11:37.283310', u'whom': u'maxim_d', u'about': u'602', u'added': u'2012-11-13T11:21:36.368063', u'what': u'new_story'}
                st,op = gso('git show %s -- %s'%(cid,s['path'])) ; assert st==0
                fnd=False
                for cmd in ['diff --git','diff --cc']:
                    if cmd in op:
                        head,fdiff = op.split(cmd)
                        fnd=True
                if not fnd:
                    print 'could not split diff "%s"'%op
                    continue
                author = re.compile('Author: (.*)').search(head).group(1) ; authormail = re.compile('<(.*)>').search(author).group(1) ; authorname = re.compile('^([^<]+) <').search(author).group(1)
                apnd = {'whom':person,'about':sid,'added':datetime.datetime.now().isoformat(),'what':'change','how':cid,'change':fdiff.split('\n'),'author':author,'author_email':authormail,'author_name':authorname}
                #print json.dumps(apnd,indent=True,sort_keys=True)
                m['notifications'].append(apnd)
                metas[s['metadata']] = m

    for fn,m in metas.items():
        print 'writing %s'%fn
        savemeta(fn,m)

    if show and not add_notifications:
        print pt
    return commits


def imp_commits(args):
    print 'importing commits.'
    if not os.path.exists(cfg.REPO_DIR): os.mkdir(cfg.REPO_DIR)
    excommits = loadcommits()
    for repo in cfg.REPOSITORIES:
        print 'running repo %s'%repo
        repon = os.path.basename(repo).replace('.git','')
        repodir = os.path.join(cfg.REPO_DIR,os.path.basename(repo))
        if not os.path.exists(repodir):
            print 'cloning.'
            cmd = 'git clone -b staging %s %s'%(repo,repodir)
            st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)
        prevdir = os.getcwd()
        os.chdir(repodir)
        #refresh the repo
        
        if not args.nofetch:
            print 'fetching at %s.'%os.getcwd()
            st,op = gso('git fetch -a') ; assert st==0,"git fetch -a returned %s\n%s"%(st,op)

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
                st,op = gso('git checkout origin/%s'%(ign)); assert st==0,"checkout origin/%s inside %s returned %s\n%s"%(ign,repodir,st,op)
                st,op = gso('git log --pretty=oneline --since=%s'%(datetime.datetime.now()-datetime.timedelta(days=30)).strftime('%Y-%m-%d')) ; assert st==0
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
            cinfo = {'s':dt,'br':[branch],'u':un,'t':task} #'repo':repon, 'cid':cid <-- these are out to save space
            if branch not in branches: branches.append(branch)
            key = '%s/%s'%(repon,cid)

            if key not in excommits: 
                excommits[key]=cinfo
            else:
                if branch not in excommits[key]['br']:
                    excommits[key]['br'].append(branch)
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

        #HEAD actually means staging in our book.
        branches = [cibr.replace('HEAD','staging') for cibr in ci['br']]
        #check if commit is on staging and exclude from other branches if so
        if 'staging' in branches: branches=['staging']


        # myrepo,cid = ck.split('/')
        # st,op = gso('cd repos/%s && git branch --contains %s'%(myrepo,cid)) ; assert st==0
        # contbranches = [cbr.strip('* ') for cbr in op.split('\n')]
        # if '(no branch)' in contbranches: contbranches.remove('(no branch)')

        if not ci['t']: continue


        repo,cid = ck.split('/')
        t = get_task(ci['t'],exc=False)
        
        if not t: 
            strans = get_story_trans()
            if ci['t'] in strans:
                print 'translating %s => %s'%(ci['t'],strans[ci['t']])
                if strans[ci['t']]=='None':
                    continue
                t = get_task(strans[ci['t']])
            else:
                print 'could not find task %s, which was referenced in %s: %s'%(ci['t'],ck,ci)
                continue

        #metadata cache
        if t['metadata'] not in metas: 
            m = loadmeta(t['metadata'])
            metas[t['metadata']]=m
            m['commits_qty']=0 #we zero it once upon load to be incremented subsequently
        else: m = metas[t['metadata']]

        dt = parsegitdate(ci['s'])

        m['commits_qty']+=1
        if not m.get('last_commit') or dt>=parsegitdate(m['last_commit']): m['last_commit']=ci['s']

        repocommiter = '-'.join([repo,ci['u']])
        if 'commiters' not in m: m['commiters']=[]
        if repocommiter not in m['commiters']: m['commiters'].append(repocommiter)
        
        for cibr in branches:
            repobranch = '/'.join([repo,cibr])
            if 'branches' not in m: m['branches']=[]
            if repobranch not in m['branches']: m['branches'].append(repobranch)



        lastdatekey = '%s-%s'%(repo,ci['u'])
        if 'lastcommits' not in m: m['lastcommits']={}
        if lastdatekey not in m['lastcommits'] or parsegitdate(m['lastcommits'][lastdatekey])<dt:
            m['lastcommits'][lastdatekey]=ci['s']

        for cibr in branches:
            lastbranchkey = '%s/%s'%(repo,cibr)
            if 'branchlastcommits' not in m: m['branchlastcommits']={}
            if lastbranchkey not in m['branchlastcommits'] or parsegitdate(m['branchlastcommits'][lastbranchkey])<dt:
                m['branchlastcommits'][lastbranchkey]=ci['s']

    print 'saving.'
    for fn,m in metas.items():
        savemeta(fn,m)
    print '%s metas touched.'%(len(metas))
def tasks_validate(tasks=None,catch=True,amend=False):
    cnt=0 ; failed=0
    tasks = [t for t in tasks if t!=None]
    p = get_participants(disabled=True)
    if tasks:
        tfs = [get_task(taskid,read=False)['path'] for taskid in tasks]
    else:
        tfs = get_task_files()
    for tf in tfs:
        try:
            t = parse_story_fn(tf,read=True,gethours=True)
            if t.get('meta') and t['meta'].get('branchlastcommits'):
                for blc in t['meta'].get('branchlastcommits'):
                    try:
                        assert '/' in blc,"%s has no /"%(blc)
                        assert 'git.ezscratch.com' not in blc,"git.ezscratch.com in %s"%(blc)
                        assert len(blc.split('/'))<=2,"%s has too many /"%(blc)
                        assert 'HEAD' not in blc,"%s has HEAD"%(blc)
                    except:
                        if amend:
                            for fn in ['lastcommits','commits_qty','branchlastcommits','commiters','last_commit','branches']:
                                if t['meta'].get(fn):
                                    del t['meta'][fn]
                            savemeta(t['metadata'],t['meta'])
                        else:
                            raise
            if t.get('person_hours'): 
                for person,hrs in t.get('person_hours'):
                    try:
                        assert '@' not in person,"%s is bad"%(person)
                    except:
                        if amend:
                            hrsfn = t['metadata'].replace('meta.json','hours.json')
                            assert os.path.exists(hrsfn)
                            savemeta(hrsfn,{})
                        else:
                            raise
            assert t['summary']
            assert t['assigned to']
            assert t['created by']
            assert t['status']
            if t['assigned to'] and t['assigned to']!='None':
                assert t['assigned to'] in p
            if t['created by'] and t['created by']!='None':
                assert t['created by'] in p
            #print '%s : %s , %s , %s, %s'%(t['id'],t['summary'] if len(t['summary'])<40 else t['summary'][0:40]+'..',t['assigned to'],t['created by'],t['status'])
            cnt+=1
        except Exception,e:
            if not catch: raise
            print 'failed validation for %s - %s'%(tf,e)
            failed+=1

    print '%s tasks in all; %s failed'%(cnt,failed)
    return failed

def rewrite(tid,o_params={},safe=True):
    assert tid
    print 'working %s'%tid
    t = get_task(tid,read=True)
    params = {'story_id':tid,
              'status':t['status'],
              'summary':t['summary'],
              'created':t['created at'],
              'creator':t['created by'],
              'tags':t['tags'],
              'assignee':t['assigned to'],
              'points':t.get('points','?'),
              'informed':t.get('informed'),
              'links':t.get('links'),
              'unstructured':t.get('unstructured','').strip(),
              'repobranch':t.get('repobranch'),
              }
    for k,v in o_params.items():
        assert k in params,"%s not in %s"%(k,params)
        params[k]=v
    cont = render('task',params)
    nowrite=False
    if safe:
        if cont!=open(t['path'],'r').read():
            print 'content of %s differs, not writing.'%t['path']
            nowrite=True
    if not nowrite:
        fp = codecs.open(t['path'],'w',encoding='utf-8') ; fp.write(cont) ; fp.close()
    tasks_validate([tid])

def make_demo(iteration,tree=False,orgmode=False):     
    from tree import Tree
    tf = [parse_story_fn(tf,read=True) for tf in get_task_files(iteration=iteration,recurse=True)]
    def tf_srt(s1,s2):
        rt=cmp(len(s1['id'].split(cfg.STORY_SEPARATOR)),len(s2['id'].split(cfg.STORY_SEPARATOR)))
        if rt!=0: return rt
        return 0
    tf.sort(tf_srt)
    tr = {'children':{}}
    tr2 = Tree('Iteration: '+iteration)
    for s in tf:
        spointer = tr
        spointer2 = tr2
        parts = s['id'].split(cfg.STORY_SEPARATOR)
        #print 'walking parts %s'%parts
        initparts = list(parts)
        joinedparts=[]
        while len(parts):
            prt = parts.pop(0)
            joinedparts.append(prt)
            tsk = get_task(cfg.STORY_SEPARATOR.join(joinedparts),read=True)
            tags = (tsk['assigned to'],)+tuple(tsk['tags'])
            summary = (tsk['summary'] if len(tsk['summary'])<80 else tsk['summary'][0:80]+'..')
            if 'priority' in tsk['tags']: summary='_%s_'%summary
            tname = ('[[file:%s][%s]]'%(tsk['path'],prt) if orgmode else prt)+' '+tsk['status']+'\t'+summary+('\t\t:%s:'%(':'.join(tags)) if len(tags) else '')
            tpt = Tree(tname)
            if prt not in spointer['children']: 
                spointer['children'][prt]={'children':{}}
                spointer2.children = spointer2.children+(tpt,)
            spointer=spointer['children'][prt]
            fnd=False
            for ch in spointer2.children:
                if ch.name==tname:
                    spointer2=ch
                    fnd=True
            assert fnd,"could not find \"%s\" in %s, initparts are %s"%(tname,[ch.name for ch in spointer2.children],initparts)
        spointer['item']={'summary':s['summary'],'assignee':s['assigned to'],'status':s['status'],'id':s['id']}
    if tree:
        print unicode(tr2)
    else:
        render('demo',{'trs':tr,'iteration':iteration,'rurl':cfg.RENDER_URL},'demo-%s.org'%iteration)
def initvars(cfg_ref):
    global commits,commitsfn,commitre,cre,are,sre,dre,cfg
    cfg=cfg_ref
    commits = {}
    commitsfn = os.path.join(cfg.DATADIR,'commits.json')
    commitre = re.compile('\[origin\/([^\]]+)\]')
    cre = re.compile('commit ([0-9a-f]{40})')
    are = re.compile('Author: ([^<]*) <([^>]+)>')
    sre = re.compile('#([0-9'+re.escape(cfg.STORY_SEPARATOR)+']+)')
    dre = re.compile('Date:   (.*)')


if __name__=='__main__':
    import config as cfg    
    initvars(cfg)

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
    pr.add_argument('--nocommit',dest='nocommit',action='store_true')

    ch = subparsers.add_parser('changes')
    ch.add_argument('--notifications',dest='notifications',action='store_true')

    git = subparsers.add_parser('fetch_commits')
    git.add_argument('--nofetch',dest='nofetch',action='store_true')
    git.add_argument('--import',dest='imp',action='store_true')
    git.add_argument('--assign',dest='assign',action='store_true')

    git = subparsers.add_parser('makedemo')
    git.add_argument('--iteration',dest='iteration',required=True)
    git.add_argument('--tree',dest='tree',action='store_true')
    git.add_argument('--orgmode',dest='orgmode',action='store_true')

    val = subparsers.add_parser('validate')
    val.add_argument('--nocatch',action='store_true',default=False)
    val.add_argument('--amend',action='store_true',default=False)
    val.add_argument('tasks',nargs='?',action='append')
    
    commit = subparsers.add_parser('commit')
    commit.add_argument('--tasks',dest='tasks',action='store_true')
    commit.add_argument('--metas',dest='metas',action='store_true')
    commit.add_argument('--hours',dest='hours',action='store_true')
    commit.add_argument('--nopush',dest='nopush',action='store_true')

    tt = subparsers.add_parser('time_tracking')
    tt.add_argument('--from',dest='from_date')
    tt.add_argument('--to',dest='to_date')

    rwr = subparsers.add_parser('rewrite')
    rwr.add_argument('--safe',dest='safe',action='store_true')
    rwr.add_argument('--iteration',dest='iteration')
    rwr.add_argument('tasks',nargs='?',action='append')

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
            t = get_task(task,read=True)
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
                    strans = get_story_trans()
                    if sid in strans:
                        print 'translating %s => %s'%(sid,strans[sid])
                        if strans[sid]=='None':
                            continue
                        t = get_task(strans[sid])
                    else:
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
        process_notifications(args)
    if args.command=='changes':
        get_changes(show=True,add_notifications=args.notifications)
    if args.command=='fetch_commits':
        if args.imp:
            imp_commits(args)
        if args.assign:
            assign_commits()
    if args.command=='makedemo':
        make_demo(iteration=args.iteration,tree=args.tree,orgmode=args.orgmode)
    if args.command=='validate':
        tasks_validate(args.tasks,catch=not args.nocatch,amend=args.amend)
    if args.command=='commit':
        prevdir = os.getcwd()
        os.chdir(cfg.DATADIR)
        st,op = gso('git pull') ; assert st==0
        commitm=[]
        if args.tasks:
            st,op = gso('git add *task.org') ; assert st==0
            commitm.append('tasks commit')
        if args.metas:
            st,op = gso('git add *meta.json') ; assert st==0
            commitm.append('metas commit')
        if args.hours:
            st,op = gso('git add *hours.json') ; assert st==0
            commitm.append('hours commit')
        st,op = gso('git status') ; assert st==0
        print op
        cmd = 'git commit -m "%s"'%("; ".join(commitm))
        st,op = gso(cmd) ; 
        if 'no changes added to commit' in op and st==256:
            print 'nothing to commit'
        else:
            assert st==0,"%s returned %s\n%s"%(cmd,st,op)
            if not args.nopush:
                cmd = 'git push'
                st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)
                print 'pushed to remote'
            os.chdir(prevdir)
    if args.command=='rewrite':
        atasks = [at for at in args.tasks if at]
        if not len(atasks):
            tasks = [parse_story_fn(tf)['id'] for tf in get_task_files(args.iteration)]
        else:
            tasks = atasks
        for tid in tasks:
            rewrite(tid,safe=args.safe)

    if args.command=='time_tracking':
        if args.from_date:from_date = datetime.datetime.strptime(args.from_date,'%Y-%m-%d').date()
        else:from_date = (datetime.datetime.now()-datetime.timedelta(days=1)).date()
        if args.to_date:to_date = datetime.datetime.strptime(args.to_date,'%Y-%m-%d').date()
        else:to_date = (datetime.datetime.now()-datetime.timedelta(days=1)).date()
        files = get_task_files()
        metafiles = [os.path.join(os.path.dirname(fn),'hours.json') for fn in files]
        agg={} ; tagg={} ; sagg={} ; pagg={} ; tcache={}

        maxparts=0
        for mf in metafiles:
            m = loadmeta(mf)
            tf=  parse_story_fn(mf)
            sid = tf['story']
            sparts = sid.split(cfg.STORY_SEPARATOR)
            tlsid = sparts[0]
            if len(sparts)>maxparts: maxparts=len(sparts)
            for k in m:
                mk = datetime.datetime.strptime(k,'%Y-%m-%d').date()
                if mk>=from_date and mk<=to_date:
                    #print mk,m[k],sid
                    for person,hours in m[k].items():
                        if sid not in agg: 
                            agg[sid]={}
                        if tlsid not in tagg:
                            tagg[tlsid]={}
                        if tlsid not in sagg:
                            sagg[tlsid]={}
                        if person not in pagg:
                            pagg[person]=0

                        if person not in agg[sid]: 
                            agg[sid][person]=0
                        
                        if person not in tagg[tlsid]:
                            tagg[tlsid][person]=0
                        if '--' not in sagg[tlsid]:
                            sagg[tlsid]['--']=0
                            
                        agg[sid][person]+=hours
                        tagg[tlsid][person]+=hours
                        sagg[tlsid]['--']+=hours
                        pagg[person]+=hours

        print '* per-Participant (time tacked) view'
        ptp = PrettyTable(['Person','Hours'])
        ptp.sortby='Hours'
        htot=0
        for person,hours in pagg.items():
            ptp.add_row([person,hours])
            htot+=hours
        ptp.add_row(['TOT',htot])
        print ptp

        for smode in ['detailed','tl','sagg']:
            headers = ['Summary','Person','Hours']
            if smode=='detailed':
                tcols = ['Task %s'%i for i in xrange(maxparts)] + headers
                mpadd=3
                cyc = agg.items()
                print '* Detailed view'
            elif smode=='tl':
                tcols = ['Task 0'] + headers
                mpadd=1
                cyc = tagg.items()
                print '* Top Level Task view'
            elif smode=='sagg':
                tcols=['Task 0']+ ['Summary','Hours']
                mpadd=0
                cyc = sagg.items()
                print '* per-Task view'
            pt = PrettyTable(tcols)
            pt.align['Summary']='l'
            hrs=0
            if smode=='sagg':
                pt.sortby='Hours'
            for sid,people in cyc:
                for person,hours in people.items():
                    if sid not in tcache:
                        tcache[sid] = get_task(sid,read=True)
                    td = tcache[sid]
                    summary = td['summary'] if len(td['summary'])<60 else td['summary'][0:60]+'..'
                    sparts = sid.split(cfg.STORY_SEPARATOR)
                    while len(sparts)<maxparts:
                        sparts.append('')
                    dt = [summary,person,"%4.2f"%hours]
                    if smode =='detailed':
                        dt=sparts+dt
                    elif smode=='tl':
                        dt=[sparts[0]]+dt
                    elif smode=='sagg':
                        dt=[sparts[0]]+[summary,hours]
                    hrs+=hours
                    pt.add_row(dt)
                if smode!='sagg':
                    pt.add_row(['--' for i in xrange(maxparts+mpadd)])
            pt.add_row(['TOT']+['--' for i in xrange(maxparts+mpadd-2)]+["%4.2f"%hrs])
            print pt
                    
