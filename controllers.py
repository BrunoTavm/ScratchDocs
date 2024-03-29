# -*- coding: utf-8 -*-
'''
filedesc: default controller file
'''
from noodles.http import Response


from tasks import gso
from config import STATUSES,RENDER_URL,DATADIR,URL_PREFIX,NOPUSH,NOCOMMIT,METASTATES
from config_local import WEBAPP_FORCE_IDENTITY
from noodles.http import Redirect,BaseResponse,Response,ajax_response
from webob import exc
from noodles.templates import render_to
from docs import initvars
import config as cfg
initvars(cfg)
from docs import cre,date_formats,parse_attrs,get_all_journals,get_fns,get_parent_descriptions,get_task,get_children,get_iterations,get_participants,rewrite,get_new_idx,add_task,get_participants,get_parent,flush_taskfiles_cache,tasks_validate,get_table_contents
from docs import loadmeta,org_render,parsegitdate,read_current_metastates,read_journal,render_journal_content,append_journal_entry,get_journals,get_tags,Task
import codecs
import copy
import datetime
import orgparse
import os
import re
import redis
import json



def get_admin(r,d):

    if WEBAPP_FORCE_IDENTITY:
        return WEBAPP_FORCE_IDENTITY
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
    return {'pts':pts,'request':request}

@render_to('tracking.html')
def tracking(request,rng):
    frto = rng.split(':') ; narr=[]
    for tel in frto:
        otel = tel
        if tel=='lastmonth': tel = (datetime.datetime.now()-datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        if tel=='lastweek': tel = (datetime.datetime.now()-datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        if tel=='yesterday': tel = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        if tel=='today': tel = (datetime.datetime.now()).strftime('%Y-%m-%d')
        narr.append(tel)
    frto = narr

    st,op = gso("find %s -type f -iname 'hours.json'"%cfg.DATADIR) ; assert st==0
    fnames = op.split("\n")
    sums={} ; tasksums={} ; tdescrs = {} ; testimates = {}
    for fn in fnames:
        tid = os.path.dirname(fn).replace(cfg.DATADIR+'/','')
        with open(fn,'r') as f: j = json.loads(f.read())
        matching = filter(lambda x: x[0]>=frto[0] and x[0]<=frto[1],j.items())
        for dt,data in matching:
            for person,hrs in data.items():
                sums[person] = sums.get(person,0)+hrs
                if person not in tasksums: tasksums[person]={}
                tasksums[person][tid] = tasksums[person].get(tid,0)+hrs
                t = get_task(tid)
                if tid not in tdescrs: tdescrs[tid] = t['summary']
                metastates,content = read_current_metastates(t,True)

                if t.get('total_hours') and metastates.get('work estimate'):
                    remaining_hours = '%4.2f'%(float(metastates.get('work estimate')['value']) - float(t.get('total_hours')))
                else:
                    remaining_hours = '--'
                testimates[tid]=remaining_hours

    sums = sums.items()
    sums.sort(lambda x,y: cmp(x[1],y[1]),reverse=True)
    return {'fr':frto[0],'to':frto[1],'tracked':sums,'tasksums':tasksums,'tdescrs':tdescrs,'testimates':testimates}

@render_to('index.html')
def iterations(request):
    its = get_iterations()
    return {'its':its,'request':request}

def asgn(request,person=None,created=None,iteration=None,recurse=True,notdone=False,query=None,tag=None,newer_than=None,recent=False,gethours=False):
    in_tasks = get_fns(assignee=person,created=created,recurse=recurse,query=query,tag=tag,newer_than=newer_than,recent=recent)
    tasks={}
    print 'got initial ',len(in_tasks),' tasks; cycling'
    for t in in_tasks:
        print 'getting parent for %s'%t._id
        tlp = get_parent(t._id,tl=True)
        assert hasattr(t,'status'),"%s with no status"%t._id
        st = t['status']
        #print 'st of %s setting to status of tlp %s: %s'%(t._id,tlp,st) 
        print 'grouping by status'
        if st not in tasks: tasks[st]=[]

        showtask=False
        if not notdone: showtask=True
        if str(t['status']) not in cfg.DONESTATES: showtask=True
        print 'showtask'
        if showtask:
            tasks[st].append(t)

    def srt(t1,t2):
        t1ids = [int(tp) for tp in (t1._id.split('/'))]
        t2ids = [int(tp) for tp in (t2._id.split('/'))]

        t1ids.insert(0,int('priority' in t1['tags']))
        t2ids.insert(0,int('priority' in t2['tags']))
        t1idsc = copy.copy(t1ids)
        t2idsc = copy.copy(t2ids)


        while True and len(t1ids) and len(t2ids):
            t1id = t1ids.pop(0)
            t2id = t2ids.pop(0)
            #print 'comparing %s & %s which were extracted from %s, %s'%(t1id,t2id,t1idsc,t2idsc)
            rt= cmp(t1id,t2id)
            if rt!=0: break
        return rt

    for st in tasks:
        tasks[st].sort(srt,reverse=True)
    return {'tasks':tasks,'statuses':STATUSES,'request':request,'gethours':gethours}

@render_to('iteration.html') 
def assignments(request,person,gethours):
    if gethours=='False': gethours=False
    rt= asgn(request,person,gethours=gethours)
    rt['headline']='Assignments for %s'%person
    return rt

@render_to('iteration.html') 
def created(request,person,gethours):
    rt= asgn(request,created=person,gethours=gethours)
    rt['headline']='Created by %s'%person
    return rt

@render_to('iteration.html')
def assignments_mode(request,person,mode,gethours):
    if mode=='notdone': notdone=True
    else: notdone =False
    rt = asgn(request,person=person,notdone=notdone,gethours=gethours)
    rt['headline']='Assignments for %s, %s'%(person,mode)
    return rt

def assignments_itn_func(request,person=None,iteration=None,mode='normal',query=None,tag=None,gethours=False):
    notdone=False
    headline=''
    if mode=='notdone':
        notdone=True
        headline+='Current Tasks'
    else:
        headline+=''
    rt=asgn(request,person=person,notdone=notdone,query=query,tag=tag,gethours=gethours)
    rt['headline']=headline
    return rt

@render_to('iteration.html')
def assignments_itn(request,person,iteration,mode='normal',tag=None):
    return assignments_itn_func(request,person,iteration,mode,tag=tag)

@render_to('iteration.html')
def index(request,gethours=False):
    rt= assignments_itn_func(request
                             ,get_admin(request,'unknown')
                             ,mode='notdone'
                             ,gethours=gethours)
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
def top_level(request):
    rt = asgn(request,recurse=False)
    rt['headline']='Top Level'
    rt['status'] = 'PARENT'
    return rt

@render_to('iteration.html')
def storage(request):
    rt = asgn(request,recurse=True)
    rt['headline']='Storage'
    rt['status'] = 'STORAGE'
    return rt

@render_to('iteration.html')
def latest(request,max_days=14,gethours=False):
    rt = asgn(request,recurse=True,recent=True,newer_than=int(max_days),gethours=gethours)
    rt['headline']='Latest created'
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
    tf = get_fns(recurse=True)
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
    return {'persons':persons,'agg':agg,'it':it,'ptasks':ptasks,'request':request}

@render_to('iteration_commits.html')
def iteration_commits(request,iteration,branch):
    gwu = cfg.GITWEB_URL
    its = get_iterations()
    it = [it for it in its if it[1]['name']==iteration][0]
    start_date = it[1]['start date']
    end_date = it[1]['end date']
    #print('commits on iteration %s to branch %s'%(iteration,branch))
    tf = get_fns(recurse=True)
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
                #print "%s has no /"%(br)
                continue
            try:
                repo,br = br.split('/')
            except ValueError:
                #print '%s has too many /'%(br)
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
                t = get_task(tid)
                task_data[tid]=t

            if tid not in lastcommits: lastcommits[tid]=stmp
            if stmp>=lastcommits[tid]: lastcommits[tid]=stmp

            if repo not in repos: repos.append(repo)
            #print(tid,repo,br,stmp)
    agg = list(agg.items())
    def lcsort(i1,i2):
        return cmp(lastcommits[i1[0]],lastcommits[i2[0]])
    agg.sort(lcsort,reverse=True)
    return {'agg':agg,'it':it,'branch':branch,'repos':repos,'gwu':gwu,'task_data':task_data,'lastcommits':lastcommits,'request':request}
    #raise Exception(metas)


def rpr(request,task,journal=False,render_only=False):
    t= get_task(task)
    if journal:        vn = 'jpath'
    else:        vn = 'path'
    cmd = 'emacs -batch --visit="%s" --funcall org-export-as-html-batch'%(t[vn])
    st,op = gso(cmd) ; assert st==0,"%s returned %s\n%s"%(cmd,st,op)

    rt = open(t[vn].replace('.org','.html'),'r').read()
    if render_only: return rt

    r = Response()
    r.body = rt
    return r

@render_to('task.html')
def task(request,task):
    if task.endswith('/'): task=task[0:-1]
    gwu = cfg.GITWEB_URL
    if task.startswith('new/'):
        under='/'.join(task.split('/')[1:])
        task='new'
    else:
        under=None
    msg=None
    adm = get_admin(request,'unknown')
    repos = [r['Name'] for r in get_table_contents(os.path.join(cfg.DATADIR,'repos.org')) if r.get('Name')]

    tags=[] ; links=[] ; informed=[] ; branches=[]
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
        if k.startswith('branches-'):
            tn = k.replace('branches-','')
            if tn in ['new-repo','new-branch']: continue
            branches.append(tn)
    lna = request.params.get('link-new-anchor')
    lnu = request.params.get('link-new-url')

    if lna and lnu:
        links.append({'anchor':lna,'url':lnu})

    inn = request.params.get('informed-new')
    if inn and inn not in informed:
        informed.append(inn)

    nrb = request.params.get('branches-new-branch','')
    assert '/' not in nrb,"branch name may not contain '/'"
    if nrb: branches.append(request.params.get('branches-new-repo')+'/'+nrb)


    tags = list(set([tag for tag in tags if tag!='']))

    uns = request.params.get('unstructured','').strip()
    if len(uns) and not uns.startswith('**'):
        uns='** Details\n'+uns
    assignees=[request.params.get('assignee')]

    if request.params.get('id') and request.params.get('id')!='None':
        t = get_task(request.params.get('id'))
        assignees.append(t.assignee)
        tid = request.params.get('id')
        o_params = {'summary':request.params.get('summary'),
                    'tags':tags,
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'unstructured':uns,
                    'links':links,
                    'informed':informed,
                    'branches':branches}
        print o_params
        rewrite(tid,o_params,safe=False,user=adm)
        t = get_task(tid)
        if request.params.get('content-journal'):
            tj = get_task(task)
            metastates={}
            append_journal_entry(tj,adm,request.params.get('content-journal'),metastates)
        assert request.params.get('id')



    if request.params.get('create'):
        o_params = {'summary':request.params.get('summary'),
                    'status':request.params.get('status'),
                    'assignee':request.params.get('assignee'),
                    'creator':get_admin(request,'unknown'),
                    'unstructured':uns,
                    'links':links,
                    'informed':informed,
                    'branches':branches}
        if request.params.get('under'):
            parent = request.params.get('under')
        else:
            parent=None
        rt = add_task(parent=parent,params=o_params,tags=tags,user=adm)
        redir = '/'+URL_PREFIX+rt._id
        print 'redircting to %s'%redir
        rd = Redirect(redir)
        return rd
    if task=='new':
        ch=[]
    else:
        ch = get_children(task)

    if task=='new':
        t = Task(created_at=None,
                 summary='',
                 unstructured='',
                 status='TODO',
                 assignee=adm,
                 creator=adm,
                 tags=[],
                 links=[],
                 branches=[],
                 journal=[])
        opar=[]
    else:
        t = get_task(task)
        par = task ; parents=[]
        parents = task.split('/')
        opar = []
        for i in xrange(len(parents)-1):
            opar.append('/'.join(parents[:i+1]))
    parents = [(pid,get_task(pid)['summary']) for pid in opar]
    prt = [r[0] for r in get_participants(sort=True)]
    metastates,content = read_current_metastates(t,True)

    # if t.get('total_hours') and metastates.get('work estimate'):
    #     remaining_hours = float(metastates.get('work estimate')['value']) - float(t.get('total_hours'))
    # elif t.get('total_hours'):
    #     remaining_hours = -1 * float(t.get('total_hours'))
    # else:
    #     remaining_hours = None
    remaining_hours=None

    #journal
    jitems = t.journal
    return {'task':t,
            'remaining_hours':remaining_hours,
            'total_hours':0,
            'j':{'%s existing entries'%t._id:jitems},
            'gwu':gwu,
            'url':RENDER_URL,
            'statuses':STATUSES,
            'participants':prt,
            'msg':msg,
            'children':ch,
            'repos':repos,
            'parents':parents,
            'request':request,
            'metastates':metastates,
            'possible_metastates':cfg.METASTATES,
            'colors':cfg.METASTATES_COLORS,
            'overrides':cfg.METASTATES_OVERRIDES,
            'diff_branches':cfg.DIFF_BRANCHES,
            'under':under,
    }

@render_to('tags.html')
def tags(request):
    tags = get_tags()
    tags = tags.items()
    tags.sort(lambda x1,x2: cmp(x1[1],x2[1]),reverse=True)
    rt = {'tags':tags}
    return rt
@render_to('iteration.html')
def bytag(request,tag):
    rt= assignments_itn_func(request
                             ,person=None
                             ,iteration=None
                             ,tag=tag
                             ,mode='normal')
    return rt

@render_to('iteration.html')
def search(request):
    rt= assignments_itn_func(request
                                ,person=None
                                ,iteration=None
                                ,mode='normal'
                                ,query=request.params.get('q'))
    return rt


@render_to('journal.html')
def global_journal(request,creator=None,day=None,groupby=None,state=None):
    adm = get_admin(request,'unknown')
    ai = []
    if day=='current': 
        daya=datetime.datetime.now().date() #strftime('%Y-%m-%d')
        day = [daya,daya]
    elif day:
        if ':' in day:
            days = day.split(':')
            daya = datetime.datetime.strptime(days[0],'%Y-%m-%d').date()
            dayb = datetime.datetime.strptime(days[1],'%Y-%m-%d').date()
            day = [daya,dayb]
        else:
            daya = datetime.datetime.strptime(day,'%Y-%m-%d').date()
            day = [daya,daya]

    print 'obtaining journals'
    gaj = get_all_journals(day)
    print 'obtained; reading %s journals'%len(gaj)
    for jt in gaj:
        if hasattr(jt,'tid'):
            ji = [jt]
            jt = get_task(jt.tid)
        else:
            ji = jt.journal
        if creator: ji = [i for i in ji if i['creator']==creator]
        if state: 
            sk,sv = state.split('=')
            ji = [i for i in ji if dict(i)['attrs'].get(sk)==sv]
        for jii in ji:
            jii['tid']=jt._id
        ai+=ji

    print 'finished reading. sorting'
    ai.sort(lambda x1,x2: cmp(x1['created_at'],x2['created_at']))
    print 'sorted'
    if groupby:
        rt={}
        for i in ai:
            assert groupby in i
            k = 'entries for %s'%i[groupby]
            if k not in rt: 
                rt[k]=[]
            rt[k].append(i)
        return {'j':rt,'task':None,'groupby':groupby,'user':adm}
    else:
        return {'j':{'all':ai},'task':None,'grouby':None,'user':adm}

@render_to('queue.html')
def queue(request,assignee=None,archive=False,metastate_group='merge'):
    if assignee=='me':
        assignee=get_admin(request,'unknown')
    queue={}
    print 'cycling journals'
    for t in get_journals():
        if assignee and t.assignee!=assignee: continue

        if metastate_group!='production':
            if not archive and t['status'] in cfg.DONESTATES: continue
            elif archive and t['status'] not in cfg.DONESTATES: continue

        tid = t._id
        #print t
        assert t.status,"could not get status for %s"%tid
        #print 'reading metastates'
        cm,content = read_current_metastates(t,True)

        #skip this task if has no metastates relevant to us
        relevant_metastates=False
        for cmk in cm:
            if cmk in cfg.METASTATES[metastate_group]:
                relevant_metastates=True
                break
        if not relevant_metastates: continue
        print 'reading journal'
        jitems = read_journal(t)
        lupd = sorted(cm.values(),lambda x1,x2: cmp(x1['updated'],x2['updated']),reverse=True)
        if len(lupd): lupd=lupd[0]['updated']
        else: lupd=None
        #any journal update takes precedence
        if len(jitems):
            try:
                jlupd = jitems[-1]['created_at']
            except:
                raise Exception(jitems[-1])
            if not lupd or jlupd >=lupd:
                lupd = jlupd
        #assert t.get('total_hours')!='None'
        print 'adding to queue'
        queue[tid]={'states':dict([(cmk,cmv['value']) for cmk,cmv in cm.items()]),
                    #'total_hours':t.get('total_hours',0),
                    'fullstates':cm,
                    'last updated':lupd,
                    'status':t['status'],
                    'summary':t['summary'],
                    'last entry':content,
                    'tags':t['tags'],
                    'assignee':t.assignee,
                    'merge':[l['url'] for l in t.links if l['anchor']=='merge doc'],
                    'job':[l['url'] for l in t.links if l['anchor']=='job'],
                    'specs':[l['url'] for l in t.links if l['anchor']=='specs']}
    print 'done. itemizing'
    queue = queue.items()
    print 'sorting'
    queue.sort(lambda x1,x2: cmp((x1[1]['last updated'] and x1[1]['last updated'] or datetime.datetime(year=1970,day=1,month=1)),(x2[1]['last updated'] and x2[1]['last updated'] or datetime.datetime(year=1970,day=1,month=1))),reverse=True)


    metastate_url_prefix = dict (zip(cfg.METASTATE_URLS.values(),cfg.METASTATE_URLS.keys()))[metastate_group]
    print 'rendering'
    return {'queue':queue,
            'metastate_group':metastate_group,
            'metastate_url_prefix':metastate_url_prefix,
            'metastates':METASTATES,
            'colors':cfg.METASTATES_COLORS,
            'overrides':cfg.METASTATES_OVERRIDES}



@render_to('journal_edit.html')
def journal_edit(request,task,jid):
    adm = get_admin(request,'unknown')
    t = get_task(task)
    if request.method=='POST':
        metastates={}
        for ms,msvals in METASTATES.items():
            msv = request.params.get(ms)
            if msv and msv in msvals:
                metastates[ms]=msv
       
        append_journal_entry(t,adm,request.params.get('content'),metastates)

        redir = '/'+URL_PREFIX+task+'/j'
        rd = Redirect(redir)
        return rd

    j = rpr(request,task,journal=True,render_only=True)

    return {'t':t,'j':j,'metastates':METASTATES}

@render_to('journal.html')
def journal(request,task):
    t = get_task(task)
    jitems = read_journal(t)
    return {'task':t,'j':{'%s existing entries'%t._id:jitems},'metastates':METASTATES}

@render_to('task_history.html')
def history(request,task):
    t = get_task(task)
    st,op = gso('git log --follow -- %s'%(os.path.join(cfg.DATADIR,task,'task.org'))) ; assert st==0
    commitsi = cre.finditer(op)
    for c in commitsi:
        cid = c.group(1)
        url = '%(gitweb_url)s/?p=%(docs_reponame)s;a=commitdiff;h=%(cid)s'%{'cid':cid,'gitweb_url':cfg.GITWEB_URL,'docs_reponame':cfg.DOCS_REPONAME}
        op = op.replace(cid,"<a href='%(url)s'>%(cid)s</a>"%{'cid':cid,'url':url})
    
    t['summary'] = ''
    rt = {'op':op,'task':t,'request':request}
    return rt

def feed_worker(request,user=None):
    if not user: user = get_admin(request,'unknown')
    r = redis.Redis('localhost')
    f = r.get('feed_'+user)
    if not f: f='[]'
    lf = json.loads(f)
    nw = datetime.datetime.now()
    for fe in lf:
        fe['when'] = datetime.datetime.strptime( fe['when'], "%Y-%m-%dT%H:%M:%S" )
        fe['delta'] = nw - fe['when']
    return {'feed':lf,'gwu':cfg.GITWEB_URL,'docs_repo':cfg.DOCS_REPONAME}

@render_to('feed_ajax.html')
def feed(request,user=None):
    return feed_worker(request,user)

@render_to('feed_fs.html')
def feed_fs(request,user=None):
    return feed_worker(request,user)

@ajax_response
def metastate_set(request):
    k = request.params.get('k')
    v = request.params.get('v')
    spl = k.split('-')
    tid = spl[1]
    msk = '-'.join(spl[2:])
    #_,tid,msk = 

    adm = get_admin(request,'unknown')
    #special case
    if msk=='work estimate':
        t = get_task(tid)
        #print '%s = %s + %s'%(msk,t['total_hours'],v)
        #v = "%4.2f"%(float(t.get('total_hours',0))+float(v))
    else:
        t =  get_task(tid)

    print 'setting %s.%s = %s'%(tid,msk,v)
    append_journal_entry(t,adm,'',{msk:v})
    return {'status':'ok'}

def favicon(request):
    response = BaseResponse()
    response.headerlist=[('Content-Type', 'image/x-icon')]
    f = open('sd/favicon.ico').read()
    response.body = f
    return response

def assets(request, r_type=None, r_file=None):
    map = {
        'css': 'text/css',
        'js': 'application/javascript',
        'fonts': 'application/octet-stream',
        'img': 'image/*',
    }
    fname = '/'.join(['sd/assets', r_type, r_file])

    if r_type not in map:
        return HTTPNotFound(fname)
    if r_file is None:
        return HTTPNotFound(fname)

    try:
        response = BaseResponse()
        f = open(fname).read()
        response.headerlist=[('Content-Type', map[r_type])]
        response.body = f
        return response
    except:
        return exc.HTTPNotFound(fname)
