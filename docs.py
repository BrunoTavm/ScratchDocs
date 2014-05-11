#!/usr/bin/env python
# coding=utf-8
import argparse

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
import time
import subprocess
import shlex
from dulwich.repo import Repo as DRepo

def org_render(ins):
    proc = subprocess.Popen([os.path.join(os.path.dirname(__file__),'orgmode-render.php')],
                            stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            close_fds=True)
    inss = ins.encode('utf-8')
    ops = proc.communicate(input=inss)[0]
    return ops.decode('utf-8')

def gso(cmd,close_fds=True,shell=False,executable=None):
    if type(cmd)==list:
        spl = cmd
    else:
        spl = shlex.split(cmd) #; spl[0]+='sadf'
    p = subprocess.Popen(spl,
                         stdout=subprocess.PIPE,
                         close_fds=close_fds,
                         shell=shell,
                         executable=executable)
    out, err = p.communicate()
    return p.returncode,out


def load_templates():
    if not os.path.exists(cfg.MAKO_DIR): os.mkdir(cfg.MAKO_DIR)
    _prefix = os.path.dirname(__file__)
    if cfg.TPLDIR:
        tpldir = cfg.TPLDIR
    else:
        tpldir = os.path.join(_prefix,'templates')
    lk = TemplateLookup(directories=['.'])
    rt = {}
    taskfn = os.path.join(tpldir,'task.org')
    assert os.path.exists(taskfn),"%s does not exist ; am in %s"%(taskfn,os.getcwd())
    rt['task'] = Template(filename=(taskfn),lookup = lk,module_directory=cfg.MAKO_DIR)
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
date_formats = ['%Y-%m-%d %a','%Y-%m-%d','%Y-%m-%d %a %H:%M']
def parse_attrs(node,pth,no_tokagg=False):
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
            for frm in date_formats:
                try:
                    rt[k]=datetime.datetime.strptime(v.strip('<>[]'),frm)
                    break
                except ValueError:
                    pass
        if k in ['created at']:
            dt = v.strip('<>[]').split('.')
            rt[k]=datetime.datetime.strptime(dt[0],'%Y-%m-%d %H:%M:%S')
            if len(dt)>1:
                rt[k]+=datetime.timedelta(microseconds=int(dt[1]))
    if not no_tokagg:
        for ta,tv in tokagg.items():
            rt[ta]=tv

    #if '338/task.org' in pth:print
    #json.dumps(rt,indent=True,default=lambda x: str(x)) ; raise
    #Exception('here it is %s'%pth)
    return rt
UNSSEP = '# UNSTRUCTURED BEYOND THIS POINT'
def parse_fn(fn,read=False,gethours=False,hoursonlyfor=None,getmeta=True,getmetastates=False):
    """parse a task filename and optionally read it."""
    assert len(fn),"%s empty"%fn
    parts = [prt for prt in fn.replace(cfg.DATADIR,'').split(cfg.STORY_SEPARATOR) if prt!='']
    assert len(parts)>1,"%s"%"error parsing %s"%fn
    story = cfg.STORY_SEPARATOR.join(parts[0:-1])
    rt = {'story':story,'path':fn,'jpath':os.path.join(os.path.dirname(fn),'journal.org'),'metadata':os.path.join(os.path.dirname(fn),'meta.json'),'id':cfg.STORY_SEPARATOR.join(parts[0:-1])}
    #raise Exception('id for %s is %s from %s'%(fn,rt['id'],parts))
    if read:
        filecont = open(fn,'r').read()
        assert fn.endswith('.org'),"bad file for orgparse %s"%fn
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
        assert tothrs!='None'
        rt['last_tracked']=last_tracked
        person_hours= person_hours.items()
        person_hours.sort(hours_srt_2)
        rt['person_hours']=person_hours
    mfn = os.path.join(os.path.dirname(fn),'meta.json')
    if getmeta:
        rt['meta']=loadmeta(mfn)
    if getmetastates:
        msfn = mfn.replace('meta.json','journal.org')
        rt['metastates']=read_current_metastates(msfn,metainfo=False)[0]
    assert rt['id']
    return rt
taskfiles_cache={}
def flush_taskfiles_cache():
    global taskfiles_cache
    taskfiles_cache={}

def filterby(fieldname,value,rtl):

    if fieldname in ['tagged']:
        values = value.split(',')
    else:
        values = [value]

    while len(values):
        value = values.pop()
        adir = os.path.join(cfg.DATADIR,fieldname,value)
        fcmd = 'find %s -type l -exec basename {} \;'%adir
        print fcmd
        st,op = gso(fcmd)  ; assert st==0,fcmd
        atids = [atid.replace('.','/') for atid in op.split('\n')]
        afiles = [os.path.join(cfg.DATADIR,atid,'task.org') for atid in atids]
        rf = set(rtl).intersection(set(afiles))
        rtl = list(rf)
    return rtl

def get_fns(assignee=None,created=None,status=None,tag=None,recurse=True,recent=False,flush=False,query=None,newer_than=None):
    """return task filenames according to provided criteria"""
    global taskfiles_cache
    if flush: flush_taskfiles_cache()

    if not recurse:
        add=' -maxdepth 2'
    else:
        add=''
    if query:        
        add2=u' -print0 | "xargs" -0 -e grep -i -e "%s" -l'%query
    else:        
        add2=''
    cmdtpl = u"find  %s  %s ! -wholename '*templates*' ! -wholename '*.git*' -type f -name '%s' %s"

    cmds = [cmdtpl%(cfg.DATADIR,add,cfg.TASKFN,add2)]
    print cmds
    files=[]
    for cmd in cmds:
        #print cmd
        s = cmd.encode('utf-8')
        ss = [s]
        st,op = gso(ss,shell=True) ;
        if not query:
            assert st==0,"%s => %s\n%s"%(cmd,st,op)
        else:
            assert st in [0,123,31488],"%s => %s\n%s"%(cmd,st,op)
        files += [fn for fn in op.split('\n') if fn!='']
    files=list(set(files))

    if assignee:
        files = filterby('assigned',assignee,files)
        print '%s files remaining after assignees filtering'%(len(files))
    if created:
        files = filterby('creators',created,files)
        print '%s files remaining after created filtering'%(len(files))
    if tag:
        files = filterby('tagged',tag,files)
        print '%s files remaining after tag filtering'%(len(files))

    #filter by assignee. heavy.
    if status or recent:
        rt = []
        for fn in files:
            s = parse_fn(fn,read=True)
            incl=False
            if assignee and s['assigned to'] and s['assigned to']==assignee:
                incl=True
            if status and s['status']==status:
                incl=True
            if status and status.startswith('not ') and status.replace('not ','')!=s['status']:
                incl=True
            if recent and 'created at' in s and s['created at']>=(datetime.datetime.now()-datetime.timedelta(days=(newer_than and newer_than or cfg.RECENT_DAYS))):
                incl=True
            if incl:
                rt.append(fn)
        return rt

    return files

def get_parent(tid,tl=False):
    spl = tid.split('/')
    if len(spl)>1:
        if tl:
            return spl[0]
        else:
            return spl[-2]
    else:
        return spl[0]

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
    cmd = 'find  %s/iterations -iname "*.org" ! -wholename "*templates*" ! -wholename "*repos/*" -type f'%(cfg.DATADIR)
    #cmd = 'find %s -maxdepth 1 ! -wholename "*.git*"  -type d'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)
    #print op  ; raise Exception('w00t')
    dirs = op.split('\n')
    rt = [(os.path.dirname(path),parse_iteration(path)) for path in dirs if len(path.split('/'))>1]
    return rt
task_cache={}
def get_task(number,read=False,exc=True,flush=False,gethours=False):
    """return everything we know about a task"""
    global task_cache
    tk = '%s-%s-%s-%s'%(number,read,exc,gethours)
    if tk in task_cache: 
        if flush: del task_cache[tk]
        else: return task_cache[tk]
    
    number = str(number)
    gtf = [os.path.join(cfg.DATADIR,number,'task.org')]
    #gtf = get_fns(recurse=True,flush=flush)

    tf = [parse_fn(fn,read=read,gethours=gethours) for fn in gtf]

    tasks = dict([(pfn['story'],pfn) for pfn in tf])    

    if exc:
        assert number in tasks,"%s (%s) not in %s"%(number,type(number),tasks.keys()) #'tasks')
    else:
        if number not in tasks: 
            return False
    rt =  tasks[number]
    task_cache[tk]=rt
    return rt
taskre = re.compile('^([\d\/]+)$')
def get_children(number):
    assert taskre.search(number),"invalid task %s"%number
    t = get_task(number)
    cmd = 'find -L %s -maxdepth 2 ! -wholename "*.git*" -type f -iname "%s" ! -wholename "%s"'%(os.path.dirname(t['path']),cfg.TASKFN,t['path'])
    st,op = gso(cmd) ; assert st==0,"%s returned %s:\n%s"%(cmd,st,op)
    chfiles = [ch for ch in op.split('\n') if ch!='']
    tf = [parse_fn(fn,read=True) for fn in chfiles]
    return tf
def get_new_idx(parent=None):
    if parent:
        t = get_task(parent)
        tpath = os.path.dirname(t['path'])
        pfx=str(parent)+'/'
    else:
        tpath = cfg.DATADIR
        pfx=''
    sids = [int(sid) for sid in (os.walk(tpath).next()[1]) if re.compile('^([\d]+)$').search(sid)]
    
    if len(sids):
        return str(max(sids)+1)
    else:
        return '1'

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

def get_participants(disabled=False,sort=False):
    tconts = get_table_contents(os.path.join(cfg.DATADIR,'participants.org'))
    rt={}
    for row in tconts:
        if disabled or row['Active']=='Y':
            rt[row['Username']]=row

    if sort:
        rt = rt.items()
        rt.sort(lambda r1,r2: cmp(r1[0],r2[0]))
    return rt

def get_story_trans():
    tconts = get_table_contents(os.path.join(cfg.DATADIR,'taskmap.org'))
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
    files = [(ln,parse_fn(ln)) for ln in op.split('\n') if ln!='']
    return files
    

def process_notifications(args=None,adm='CLI'):
    if not args:
        class Args(object):
            renotify=False
            nonotify=cfg.NONOTIFY
            nocommit=cfg.NOCOMMIT
        args = Args()
    tfs = get_meta_files()
    files_touched=[]
    participants = get_participants(disabled=True)
    if args.renotify:
        newer_than = datetime.datetime.strptime(args.renotify,'%Y-%m-%d')
    else:
        newer_than = None

    for meta,s in tfs:
        m = loadmeta(meta)
        if m.get('notifications'):
            for n in m['notifications']:
                if n.get('notified') and not args.renotify:
                    continue
                if newer_than:
                    added = datetime.datetime(*time.strptime(n['added'].split('.')[0], "%Y-%m-%dT%H:%M:%S")[:6])
                    if not added>=newer_than:
                        continue
                #print 'notification processing %s'%s
                whom = participants[n['whom']]
                if whom['E-Mail']!=n.get('author_email') and whom['Active']=='Y':
                    send_notification(n['whom'],n['about'],n['what'],n.get('how'),body=n,nonotify=args.nonotify)
                else:
                    #print 'silencing notify about a commit by %s to %s'%(n['author'],n['whom'])
                    pass
                n['notified']=datetime.datetime.now().isoformat()
                savemeta(meta,m)
                files_touched.append(meta)
    if len(files_touched) and not args.nocommit:
        print 'commiting %s touched files.'%(len(files_touched))
        from tasks import pushcommit
        pushcommit.delay(files_touched,None,adm)
        cmd = ['cd %s && git add '%cfg.DATADIR+' '.join(files_touched)+' && git commit -m "automatic commit of updated metafiles."']
        if not cfg.NOPUSH: cmd[0]+=' && git push'
        st,op = gso(cmd,shell=True) ; assert st==0,"%s returned %s:\n%s"%(cmd,st,op)

def parse_change(t,body,descr=True):
    ch = body.get('change',[])
    if u'--- /dev/null' in ch:
        verb='created'
    else:
        verb='changed'
    if descr:
        app = u' - %s'%t['summary']
    else:
        app = u''
    stchangere=re.compile('^(\-|\+)\* (%s)'%'|'.join(cfg.STATUSES))
    stch = filter(lambda r: stchangere.search(r),ch)
    canlines=0
    if len(stch)==2:
        sw = stchangere.search(stch[0]).group(2)
        sn = stchangere.search(stch[1]).group(2)
        scdigest=('%s -> %s'%(sw,sn))
        app+='; %s'%scdigest
        canlines+=1
    asgnchangere=re.compile('^(\-|\+)'+re.escape('- assigned to :: ')+'(.+)')
    asch = filter(lambda r: asgnchangere.search(r),ch)
    if len(asch)==2:
        aw = asgnchangere.search(asch[0]).group(2)
        an = asgnchangere.search(asch[1]).group(2)
        asdigest=('reassigned %s -> %s'%(aw,an))
        app+='; %s'%asdigest
        canlines+=1
    laddre = re.compile('^(\+)')
    laddres = filter(lambda r: not r.startswith('+++') and laddre.search(r) or False,ch[4:]) #skipping diff header
    lremre = re.compile('^(\-)')
    lremres = filter(lambda r: not r.startswith('+++') and lremre.search(r) or False,ch[4:]) #skipping diff header
    if len(laddres)==len(lremres):
        if canlines!=len(laddres):
            app+='; %sl'%(len(laddres))
    elif verb=='changed':
        app+=';'
        if len(laddres): app+=' +%s'%len(laddres)
        if len(lremres):  app+='/-%s'%len(lremres)
    subject = '%s ch. by %s'%(t['story'],body.get('author_username','Uknown'))+app
    return subject

def send_notification(whom,about,what,how=None,justverify=False,body={},nonotify=False):
    import sendgrid # we import here because we don't want to force everyone installing this.
    assert cfg.RENDER_URL,"no RENDER_URL specified in config."
    assert cfg.SENDER,"no sender specified in config."

    p = get_participants()
    try:
        email = p[whom]['E-Mail']
    except KeyError:
        #print '%s not in %s'%(whom,p.keys())
        return False
    t= get_task(about,read=True)
    tpl = what+'_notify'
    tf = tempfile.NamedTemporaryFile(delete=False,suffix='.org')

    #try to figure out what changed
    subject = parse_change(t,body)

    #construct the rendered mail template informing of the change
    if what=='change':

        assert cfg.GITWEB_URL
        assert cfg.DOCS_REPONAME
        rdt = {'t':t,'url':cfg.RENDER_URL,'recipient':p[whom],'commit':how,'gitweb':cfg.GITWEB_URL,'docsrepo':cfg.DOCS_REPONAME,'body':body}
    elif what in ['new_story']:
        return False
    else:
        raise Exception('unknown topic %s for %s'%(what,about))
    notify = render(tpl,rdt,tf.name)
    #print open(tf.name,'r').read() ; raise Exception('bye')
    if justverify:
        return False
    cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(tf.name)
    st,op = gso(cmd) ; assert st==0,cmd
    expname = tf.name.replace('.org','.html')
    #print 'written %s'%expname
    assert os.path.exists(expname)
    s = sendgrid.Sendgrid(cfg.SENDGRID_USERNAME,cfg.SENDGRID_PASSWORD,secure=True)
    if body and body.get('authormail'):
        sender = body.get('authormail')
    else:
        sender = cfg.SENDER
    subject_utf8 = subject.encode('utf-8')
    message = sendgrid.Message(sender,subject_utf8,open(tf.name).read(),open(expname).read())
    message.add_to(email,p[whom]['Name'])
    if not cfg.NONOTIFY and not nonotify: 
        s.web.send(message)
    return True
def add_iteration(name,start_date=None,end_date=None):
    raise Exception('TODO')
    itdir = os.path.join(cfg.DATADIR,name)
    itfn = os.path.join(itdir,'iteration.org')
    assert not os.path.exists(itdir),"%s exists."%itdir
    os.mkdir(itdir)
    render('iteration',{'start_date':start_date,'end_date':end_date},itfn)

def add_task(parent=None,params={},force_id=None,tags=[]):
    print 'in add_task'
    if parent:
        print 'is a child task'
        tf = [parse_fn(fn,getmeta=False) for fn in get_fns(flush=True)]
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
        print 'is a top level task'
        basedir = os.path.join(cfg.DATADIR)
        if force_id:
            #make sure we don't have it already
            tf = [parse_fn(fn)['story'] for fn in get_fns()]
            assert str(force_id) not in tf,"task %s already exists - %s."%(force_id,get_task(force_id))
            newidx = str(force_id)
        else:
            print 'getting a new index'
            newidx = get_new_idx()
            print 'done getting a new index'
        newdir = os.path.join(basedir,newidx)
        fullid = cfg.STORY_SEPARATOR.join([newidx])
        newtaskfn = os.path.join(newdir,'task.org')
    print 'parsing new task fn'
    newtaskdt = parse_fn(newtaskfn)
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

    for ai in cfg.ALWAYS_INFORMED:
        if ai not in pars['informed']: pars['informed'].append(ai)

    assert not os.path.exists(newdir),"%s exists"%newdir
    dn = os.path.dirname(newdir)
    assert os.path.exists(dn),"%s does not exist."%dn
    os.mkdir(newdir)

    assert not os.path.exists(newtaskfn)
    pars['tags']=tags
    print 'rendering'
    render('task',pars,newtaskfn)
    pars['path']=newtaskfn
    print 'clearing the cache for tasks'
    global task_cache,taskfiles_cache
    task_cache={}
    taskfiles_cache={}
    pars['id']=fullid
    print 'done creating'
    return pars

def makehtml(notasks=False,files=[]):
    #find all the .org files generated

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
    raise Exception('TODO')
    nw = datetime.datetime.now() ; current_iteration=None
    for itp,it in iterations:
        if ('start date' in it and 'end date' in it):
            if (it['start date'].date()<=nw.date() and it['end date'].date()>=nw.date()):
                current_iteration = (itp,it)
    assert current_iteration,"no current iteration"
    return current_iteration

def makeindex():
    recent = [(tf,parse_fn(tf,read=True,gethours=True)) for tf in get_fns(recent=True)]
    recent.sort(hours_srt,reverse=True)
        
    assignees={}
    #create the dir for shortcuts
    if not os.path.exists(cfg.SDIR): os.mkdir(cfg.SDIR)

    #and render its index in the shortcuts folder
    idxstories = [(fn,parse_fn(fn,read=True,gethours=True)) for fn in get_fns(recurse=True)]
    vardict = {'term':'Index','value':'','stories':by_status(idxstories),'relpath':True,'statuses':cfg.STATUSES,'statusagg':{}}
    routfile= os.path.join(cfg.SDIR,'index.org')
    #print 'rendering %s'%routfile
    render('tasks',vardict,routfile)

    #print 'walking iteration %s'%it[0]
    taskfiles = get_fns(recurse=True)
    stories = [(fn,parse_fn(fn,read=True,gethours=True)) for fn in taskfiles]
    stories_by_id = dict([(st[1]['id'],st[1]) for st in stories])
    stories.sort(taskid_srt,reverse=True)        

    #let's create symlinks for all those stories to the root folder.
    for tl in stories:
        tpath = tl[0]
        taskid = '-'.join(tl[1]['story'].split(cfg.STORY_SEPARATOR))
        spath = os.path.join(cfg.SDIR,taskid)
        dpath = '/'+tl[1]['story']
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

            tf = get_fns(assignee=assignee,recurse=True)
            stories = [(fn,parse_fn(fn,read=True,gethours=True,hoursonlyfor=assignee)) for fn in tf]
            stories.sort(status_srt)
            vardict = {'term':'Assignee','value':'%s (%s)'%(assignee,storycnt),'stories':by_status(stories),'relpath':False,'statuses':cfg.STATUSES,'statusagg':{}}
            cont = render('tasks',vardict,ofn)


    vardict = {
               'stories':stories,
               'assigned_files':assigned_files,
               'assignees':assignees,
               'recent_tasks':recent,
               'statusagg':{}
               }
    idxfn = os.path.join(cfg.DATADIR,'index.org')
    itlist = render('iterations',vardict,idxfn)

    cfn = os.path.join(cfg.DATADIR,'changes.org')
    render('changes',{'GITWEB_URL':cfg.GITWEB_URL,'DOCS_REPONAME':cfg.DOCS_REPONAME,'changes':get_changes(),'pfn':parse_fn},cfn)

def list_stories(iteration=None,assignee=None,status=None,tag=None,recent=False):
    files = get_fns(assignee=assignee,status=status,tag=tag,recent=recent)
    pt = PrettyTable(['id','summary','assigned to','status','tags'])
    pt.align['summary']='l'
    cnt=0
    for fn in files:
        sd = parse_fn(fn,read=True)
        if iteration and iteration.startswith('not ') and sd['iteration']==iteration.replace('not ',''): 
            continue
        elif iteration and not iteration.startswith('not ') and sd['iteration']!=str(iteration): continue
        if len(sd['summary'])>60: summary=sd['summary'][0:60]+'..'
        else: summary = sd['summary']
        pt.add_row([sd['story'],summary,sd['assigned to'],sd['status'],','.join(sd.get('tags',''))])
        cnt+=1
    pt.sortby = 'status'
    print pt
    print '%s stories.'%cnt

def tokenize(n):
    return '%s-%s'%(n['whom'],n.get('how'))

def notifications_feed_populate(notify,commits):
    import redis
    r = redis.Redis('localhost')
    feeds={}
    for rsid,people in notify.items():
        sid,overwhat = rsid.split('::')
        for person,pcommits in people.items():
            for cid in pcommits:
                t=  get_task(sid,read=True)
                commits[cid]['change']=get_commit_task_diff(cid,overwhat,t,commits)[1]
                subj = parse_change(t,commits[cid],descr=False)
                print '<%s> %s : change of %s %s => %s : %s'%(commits[cid]['commit_time'],cid[0:4],overwhat,sid,person,subj)
                if person not in feeds: feeds[person]=[]
                feeds[person].append({'sid':sid,
                                      'when':commits[cid]['commit_time'],
                                      'what':overwhat,
                                      'cid':cid,
                                      'subj':subj})
    for p,f in feeds.items():
        f.sort(lambda x,y: cmp(x['when'],y['when']),reverse=True)
        dthandler = lambda obj: obj.isoformat() if isinstance(obj, datetime.datetime)  or isinstance(obj, datetime.date) else None
        r.set('feed_'+p,json.dumps(f,indent=True,default=dthandler))

                
def get_commit_task_diff(cid,overwhat,s,commits):
    if overwhat=='task':
        pth = s['path']
    elif overwhat=='journal':
        pth = s['jpath']
    else: raise Exception('unknown notify topic %s'%overwhat)

    cmd = ['cd %s && git show %s -- %s'%(cfg.DATADIR,cid,pth)]
    st,op = gso(cmd,shell=True) ; assert st==0,"%s returned %s - at %s\n%s"%(cmd,st,os.getcwd(),op)
    fnd = False ; head = None ; fdiff = None
    for gcmd in ['diff --git','diff --cc']:
        if gcmd in op:
            head,fdiff = op.split(gcmd)
            fnd=True
            break
    return fnd,head,fdiff

def whom_to_notify(pfn,participants):
    pinf={}
    for p,pv in participants.items():
        if pv.get('Informed'): 
            pinf[p]= set(pv['Informed'].strip().split(','))
    whoms=[]
    for fn in ['created by','assigned to','informed']:
        if not pfn.get(fn) or pfn.get('fn')=='None':
            continue
        if fn=='informed':
            apnd = pfn.get(fn)
        else:
            apnd = [pfn.get(fn)]
        whoms+=apnd
        #notify anyone with a tag alert
        for twhom,ttags in pinf.items():
            tag_inter = pfn['tags'].intersection(ttags)
            if len(tag_inter):
                if twhom not in whoms: 
                    #print 'notifying %s over tag subscription %s'%(twhom,tag_inter)
                    whoms.append(twhom)
    if not whoms: raise Exception(pfn['created by'],pfn.get('assigned to'),pfn.get('informed'))
    return whoms

def notifications_metas_populate(notifyover,commits,participants):
    metas={}
    print '%s notifyover'%len(notifyover)
    for rsid,people in notifyover.items():
        sid,overwhat = rsid.split('::')
        for person,pcommits in people.items():
            for cid in pcommits:
                #print('in commit %s, story %s, person %s'%(cid,sid,person))
                if not sid: continue
                s = get_task(sid)
                if s['metadata'] in metas:
                    m = metas[s['metadata']]
                else:
                    m = loadmeta(s['metadata'])
                if 'notifications' not in m: m['notifications']=[]
                toks = [tokenize(n) for n in m['notifications']]
                mytok = '%s-%s'%(person,cid)

                if mytok in toks: 
                    #print '%s in %s : %s'%(mytok,len(toks),[noti for noti in m['notifications'] if tokenize(noti)==mytok])
                    continue

                fnd,head,fdiff = get_commit_task_diff(cid,overwhat,s,commits)

                if not fnd:
                    print 'could not split diff "%s for %s: %s"'%(op,s['path'],cmd)
                    continue

                author = commits[cid]['author']
                authorname = commits[cid]['author_name']
                authormail = commits[cid]['author_email']
                authorun = [pse[0] for pse in participants.items() if pse[1]['E-Mail']==authormail]
                if len(authorun): 
                    authorun=authorun[0]
                else:
                    authorun=None
                apnd = {'whom':person,
                        'about':sid,
                        'added':datetime.datetime.now().isoformat(),
                        'what':'change',
                        'how':cid,
                        'change':fdiff.split('\n'),
                        'author':author,
                        'author_email':authormail,
                        'author_name':authorname,
                        'author_username':authorun}
                #print json.dumps(apnd,indent=True,sort_keys=True)
                m['notifications'].append(apnd)
                metas[s['metadata']] = m
    return metas

def get_changes(show=False,add_notifications=False,feed=False,changes_limit=200):

    R = DRepo(cfg.DATADIR)
    op = [opo for opo in R.revision_history(R.head())[0:changes_limit]]
    ps = get_participants()

    commits={}
    for opo in op:
        author = opo.author
        authormail = re.compile('<(.*)>').search(author).group(1)
        authorname = re.compile('^([^<]+) <').search(author).group(1)
        authorun = [pse[0] for pse in ps.items() if pse[1]['E-Mail']==authormail]
        if len(authorun): 
            authorun=authorun[0]
        else: authorun=None

        commits[opo.sha().hexdigest()]={'message':opo.message,
                                        'commit_time':datetime.datetime.fromtimestamp(opo.commit_time),
                                        'author':opo.author,
                                        'author_username':authorun,
                                        'author_email':authormail,
                                        'author_name':authorname}

    assert len(op)==len(commits),commits
    print len(commits),'commits'

    commitsi = commits.items()
    for cid,cmsg in commitsi:

        #print 'working commit %s / %s'%(cid,len(commitsi))
        o = R.get_object(cid)
        commits[cid]['date']=datetime.datetime.fromtimestamp(o.commit_time)
        cmd = ["cd %s && git show %s"%(cfg.DATADIR,cid)] # | egrep '^(\-\-\-|\+\+\+)' | egrep
        st,op = gso(cmd,shell=True) ; assert st==0,"%s returned %s"%(cmd,st)
        ops = op.split('\n')
        lines = filter(lambda s: ((s.startswith('---') or s.startswith('+++')) and '/dev/null' not in s and s.endswith('.org')),ops)
        ulines=[]
        for l in lines:
            for r in ['--- a/','+++ a/','--- b/','+++ b/']: l=l.replace(r,'')
            if l not in ulines: 
                ulines.append(l)
        commits[cid]['changes']=ulines



    pt = PrettyTable(['date','commit','author','message','file','story'])
    notifyover={}
    for cid,cdata in commits.items():
        #print 'going over commit %s which has %s
        #changes'%(cid,len(cdata['changes']))
        for cfn in cdata['changes']:
            if os.path.exists(os.path.join(cfg.DATADIR,cfn)) and os.path.basename(cfn) not in ['participants.org']:
                if os.path.basename(cfn)=='journal.org':
                    toreadfn = cfn.replace('journal.org','task.org')
                    overwhat='journal'
                else:
                    toreadfn = cfn
                    overwhat='task'

                pfn = parse_fn(os.path.join(cfg.DATADIR,toreadfn),read=True)
                sid = pfn['id']
            else:
                pfn = None
                sid = None
            pt.add_row([cdata['date'],cid[0:4],cdata['author_username'] and cdata['author_username'] or cdata['author'],cdata['message'],cfn,sid])

            if '@DONTNOTIFY' in cdata['message'] or (not add_notifications and not feed) or not pfn:
                skp=True
            else:
                skp = False
            #print 'skip = %s ; %s %s notify %s %s %s'%(skp,cid,cfn,'@DONTNOTIFY' in cdata['message'],add_notifications,pfn==None)
            if skp: continue
            whoms = whom_to_notify(pfn,ps)

            #notify people related to the task
            for whom in whoms:
                if cdata['author_username']==whom: 
                    continue
                tok = sid+'::'+overwhat
                if not whom or whom=="None": continue
                if tok not in notifyover:
                    notifyover[tok]={}
                if whom not in notifyover[tok]:
                    notifyover[tok][whom]=[]
                if cid not in  notifyover[tok][whom]:
                    notifyover[tok][whom].append(cid)


    if feed: notifications_feed_populate(notifyover,commits)


    if add_notifications:
        metas = notifications_metas_populate(notifyover,commits,participants=ps)
        for fn,m in metas.items():
            print 'writing %s'%fn
            savemeta(fn,m)

    if show and not (add_notifications or feed):
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
def tasks_validate(tasks=None,catch=True,amend=False,checkhours=True,checkreponames=True):
    cnt=0 ; failed=0
    tasks = [t for t in tasks if t!=None]
    p = get_participants(disabled=True)
    firstbad=None
    if tasks:
        tfs = [get_task(taskid,read=False)['path'] for taskid in tasks]
    else:
        tfs = get_fns()
    for tf in tfs:
        try:
            t = parse_fn(tf,read=True,gethours=True)
            if checkreponames and t.get('meta') and t['meta'].get('branchlastcommits'):
                for blc in t['meta'].get('branchlastcommits'):
                    try:
                        assert '/' in blc,"%s has no /"%(blc)
                        assert 'git.ezscratch.com' not in blc,"git.ezscratch.com in %s"%(blc)
                        assert len(blc.split('/'))<=2,"%s has too many /"%(blc)
                        assert 'HEAD' not in blc,"%s has HEAD"%(blc)
                    except Exception,e:
                        if amend:
                            print 'amending %s'%e
                            for fn in ['lastcommits','commits_qty','branchlastcommits','commiters','last_commit','branches']:
                                if t['meta'].get(fn):
                                    del t['meta'][fn]
                            savemeta(t['metadata'],t['meta'])
                        else:
                            raise
            if t.get('meta') and t['meta'].get('commiters'):
                for blc in t['meta'].get('commiters'):
                    br,person = blc.split('-')
                    assert '.' not in person,"bad commiter - %s"%person

            if checkhours and t.get('person_hours'): 
                for person,hrs in t.get('person_hours'):
                    try:
                        assert '@' not in person,"hours in person: %s is bad"%(person)
                    except Exception,e:
                        if amend:
                            print 'amending %s'%e
                            hrsfn = t['metadata'].replace('meta.json','hours.json')
                            hrsm = loadmeta(hrsfn)
                            for hdt,items in hrsm.items():
                                if person in items:
                                    if not firstbad or hdt<firstbad: firstbad=hdt

                            hrsfn = hrsfn
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
            #checking for dupes
            cmd = "find %s -type f -iregex '^([^\]+)/%s$'"%(cfg.DATADIR,'/'.join([t['id'],'task.org']))
            st,op = gso(cmd) ; assert st==0
            dfiles = op.split('\n')
            assert len(dfiles)==1,"%s is not 1 for %s"%(dfiles,cmd)
            #print '%s : %s , %s , %s, %s'%(t['id'],t['summary'] if len(t['summary'])<40 else t['summary'][0:40]+'..',t['assigned to'],t['created by'],t['status'])
            cnt+=1
        except Exception,e:
            if not catch: raise
            print 'failed validation for %s - %s'%(tf,e)
            failed+=1

    print '%s tasks in all; %s failed; firstbad=%s'%(cnt,failed,firstbad)
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
    tf = [parse_fn(tf,read=True) for tf in get_fns(iteration=iteration,recurse=True)]
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

    
def index_assigned(tid=None,dirname='assigned',idxfield='assigned to'):
    asgndir = os.path.join(cfg.DATADIR,dirname)
    if tid:
        st,op = gso('find %s -type l -iname %s -exec rm {} \;'%(asgndir,tid.replace('/','.'))) ; assert st==0
        tfs = [get_task(tid)['path']]
    else:
        tfs = get_fns()
        st,op = gso('rm -rf %s/*'%(asgndir)) ; assert st==0


    assert os.path.exists(asgndir),"%s does not exist"%asgndir

    print 'reindexing %s task files'%(len(tfs))
    acnt=0
    for fn in tfs:
        #print 'parsing %s'%fn
        pfn = parse_fn(fn,read=False,getmeta=False)
        #print 'parsed %s ; getting task'%pfn['id']
        t = get_task(pfn['id'],read=True)
        #print t['id'],t['assigned to']
        if type(t[idxfield]) in [unicode,str]:
            myidxs=[t[idxfield]]
        else:
            myidxs=t[idxfield]

        for myidx in myidxs:
            blpath = os.path.join(asgndir,myidx)
            if not os.path.exists(blpath):
                st,op = gso('mkdir %s'%blpath) ; assert st==0
                acnt+=1
            tpath = os.path.join(blpath,t['id'].replace('/','.'))
            lncmd = 'ln -s %s %s'%('../../'+fn,tpath)
            #print lncmd
            st,op = gso(lncmd) ; assert st==0
    print 'indexed under %s %s'%(acnt,idxfield)
        
def index_tasks(tid=None):
    index_assigned(tid,'creators','created by') #task creator
    index_assigned(tid) #index task assignment
    index_assigned(tid,'tagged','tags') #index tagging


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

    idx = subparsers.add_parser('reindex')
    
    lst = subparsers.add_parser('list')
    lst.add_argument('--assignee',dest='assignee')
    lst.add_argument('--status',dest='status')
    lst.add_argument('--tag',dest='tag')
    lst.add_argument('--recent',dest='recent',action='store_true')

    gen = subparsers.add_parser('index')

    html = subparsers.add_parser('makehtml')
    html.add_argument('--notasks',dest='notasks',action='store_true')
    html.add_argument('files',nargs='*')

    nw = subparsers.add_parser('new')
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
    pr.add_argument('--nonotify',dest='nonotify',action='store_true')
    pr.add_argument('--renotify',dest='renotify')


    ch = subparsers.add_parser('changes')
    ch.add_argument('--notifications',dest='notifications',action='store_true')
    ch.add_argument('--feed',dest='feed',action='store_true')

    git = subparsers.add_parser('fetch_commits')
    git.add_argument('--nofetch',dest='nofetch',action='store_true')
    git.add_argument('--import',dest='imp',action='store_true')
    git.add_argument('--assign',dest='assign',action='store_true')

    git = subparsers.add_parser('makedemo')
    git.add_argument('--tree',dest='tree',action='store_true')
    git.add_argument('--orgmode',dest='orgmode',action='store_true')

    val = subparsers.add_parser('validate')
    val.add_argument('--nocatch',action='store_true',default=False)
    val.add_argument('--nocheckhours',action='store_true',default=False)
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
    rwr.add_argument('tasks',nargs='?',action='append')

    args = parser.parse_args()

    if args.command=='list':
        list_stories(assignee=args.assignee,status=args.status,tag=args.tag,recent=args.recent)
    if args.command=='reindex':
        index_tasks()
    if args.command=='index':
        makeindex()
    if args.command=='makehtml':
        makehtml(notasks=args.notasks,files=args.files)

    if args.command=='new':
        task = add_task(parent=args.parent,params=args,force_id=args.id,tags=args.tags)
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
                if not os.path.exists(t['path']):
                    badfn = os.path.join(cfg.DATADIR,'tracked-bad.json')
                    if os.path.exists(badfn):
                        bad = json.loads(open(badfn,'r').read())
                    else:
                        bad = {}
                    for date,tracking in hours.items():
                        if date not in bad: bad[date]={}
                        for person,p_hours in tracking.items():
                            if person not in bad[date]: bad[date][person]={}
                            bad[date][person][sid]=p_hours

                    print 'NONEXISTENT TASK %s'%sid,hours
                    fp = open(badfn,'w') ; fp.write(json.dumps(bad,indent=True,sort_keys=True)) ; fp.close()
                else:
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
        get_changes(show=True,add_notifications=args.notifications,feed=args.feed)
    if args.command=='fetch_commits':
        if args.imp:
            imp_commits(args)
        if args.assign:
            assign_commits()
    if args.command=='makedemo':
        make_demo(tree=args.tree,orgmode=args.orgmode)
    if args.command=='validate':
        tasks_validate(args.tasks,catch=not args.nocatch,amend=args.amend,checkhours = not args.nocheckhours)
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
            tasks = [parse_fn(tf)['id'] for tf in get_fns()]
        else:
            tasks = atasks
        for tid in tasks:
            rewrite(tid,safe=args.safe)

    if args.command=='time_tracking':
        if args.from_date:from_date = datetime.datetime.strptime(args.from_date,'%Y-%m-%d').date()
        else:from_date = (datetime.datetime.now()-datetime.timedelta(days=1)).date()
        if args.to_date:to_date = datetime.datetime.strptime(args.to_date,'%Y-%m-%d').date()
        else:to_date = (datetime.datetime.now()-datetime.timedelta(days=1)).date()
        files = get_fns()
        metafiles = [os.path.join(os.path.dirname(fn),'hours.json') for fn in files]
        agg={} ; tagg={} ; sagg={} ; pagg={} ; tcache={}

        maxparts=0
        for mf in metafiles:
            m = loadmeta(mf)
            tf=  parse_fn(mf)
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
                    

def get_parent_descriptions(tid):
    assert tid
    #print 'getting parent descriptions of %s'%tid
    #obtain parent descriptions
    parents = tid.split('/')
    opar=[]
    for i in xrange(len(parents)-1): opar.append('/'.join(parents[:i+1]))
    parents = [(pid,get_task(pid,read=True)['summary']) for pid in opar]
    return parents

def read_current_metastates_worker(items,metainfo=False):
    rt={} ; 
    for i in items:
        if i.get('content'):
            content={'value':i['rendered_content'],
                     'raw':i['content'],
                     'updated':i['created at'],
                     'updated by':i['creator']}
        for attr,attrv in i['attrs'].items():
            if metainfo:
                rt[attr]={'value':attrv,
                          'updated':i['created at'],
                          'updated by':i['creator']}
            else:
                rt[attr]=attrv
    return rt


def read_current_metastates(jfn,metainfo=False):
    content=None
    items = read_journal(jfn)
    return read_current_metastates_worker(items,metainfo),content


def read_journal(jfn,date_limit=None,state_limit=None):
    if jfn:
        tid = parse_fn(jfn,read=False,gethours=False,getmeta=False)['story']
    else:
        tid = None
    if jfn and os.path.exists(jfn):
        items=[]
        root = orgparse.load(jfn)
        heading = None ; creator = None ; gotattrs=False ; unstructured='' ; attrs = {}
        for node in root[1:]:
            #print 'NODE',node
            if node.level==2: 
                if heading:
                    #print 'encountered new heading; appending'
                    #get rid of previous data item
                    assert unstructured or len(attrs)
                    apnd = {'tid':tid,
                            'creator':creator,
                            'attrs':attrs,
                            'created at':created,
                            'content':unstructured.decode('utf-8'),
                            'rendered_content':org_render(unstructured.decode('utf-8'))}
                    items.append(apnd)
                heading = None ; creator = None ; gotattrs=False ; unstructured='' ; attrs = {} ; unstructured = '\n'.join(str(node).split('\n')[1:])
                heading = node.get_heading() 
                assert heading.startswith('<'),"heading does not contain date: %s"%heading
                creator = node.tags.pop()
                created = datetime.datetime.strptime(heading.strip('<>'),date_formats[2])
                #print 'gotten heading %s , %s'%(creator,created)
            elif node.level==3 and node.get_heading().lower()=='attributes':
                attrs = parse_attrs(str(node),jfn,no_tokagg=True)
                gotattrs=True
            elif node.level==3 and node.get_heading().lower()=='content':
                #print 'adding unstructured'
                unstructured+='\n'.join(str(node).split('\n')[1:])+'\n'
        apnd = {'tid':tid,
                'creator':creator,
                'attrs':attrs,
                'created at':created,
                'content':unstructured.decode('utf-8'),
                'rendered_content':org_render(unstructured.decode('utf-8'))}
        items.append(apnd)
        if date_limit: 
            if type(date_limit)==list:
                items = [i for i in items if i['created at'].date()>=date_limit[0] and i['created at'].date()<=date_limit[1]]
            else:
                items = [i for i in items if i['created at'].date()==date_limit]
        if state_limit:
            if '=' in state_limit:
                stlk,stlv = state_limit.split('=')
                items = [i for i in items if i['attrs'].get(stlk)==stlv]
            else:
                items = [i for i in items if i['attrs'].get(state_limit)]
        return items
    else:
        return []

def get_all_journals():
    cmd = 'find %s -name "journal.org" -type f'%cfg.DATADIR
    st,op = gso(cmd) ; assert st==0
    return [fn for fn in op.split('\n') if fn!='']

def render_journal_content(user,content,metastates):
    now = datetime.datetime.now()
    cnt = """\n** <%s> :%s:\n"""%(now.strftime(date_formats[2]),user)
    if len(metastates):
        cnt+="*** Attributes\n"
        for ms,msv in metastates.items():
            cnt+="- %s :: %s\n"%(ms,msv)
    if len(content):
        cnt+="*** Content\n"
        cnt+=content.replace('\r','')+'\n'
    return cnt

def append_journal_entry(task,adm,content,metastates={}):
    from tasks import pushcommit

    assert len(metastates) or len(content)
    for k,v in metastates.items():
        assert k in cfg.METASTATES_FLAT,"%s not in metastates"%k
        if type(cfg.METASTATES_FLAT[k])==tuple:
            assert v in cfg.METASTATES_FLAT[k],"%s not in %s"%(v,cfg.METASTATES_FLAT[k])
        else:
            inptp,inpstp = cfg.METASTATES_FLAT[k].split('(')
            inpstp = inpstp.split(')')[0]
            if inptp=='INPUT':
                if inpstp=='number': assert re.compile('^([0-9\.]+)$').search(v)
                else: raise Exception('unknown inpstp %s'%inpstp)
            else:
                raise Exception('unknown inptp %s'%inptp)
    tid = task['id']
    jfn = task['jpath']
    if not os.path.exists(jfn): #put a header in it
        open(jfn,'a').write('#+OPTIONS: toc:nil        (no default TOC at all)\n#+STARTUP:showeverything')

    apnd = render_journal_content(adm,content,metastates)
    fp = codecs.open(jfn,'a',encoding='utf-8')
    fp.write(apnd)
    fp.close()
    pushcommit.delay(jfn,tid,adm)
