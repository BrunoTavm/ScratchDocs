from couchdbkit import *
from jsoncompare import compare

def init_conn():
    #print 'creating server'
    import config as cfg
    s = Server(uri=cfg.COUCHDB_URI)
    #print 'obtaining db'
    d = s.get_or_create_db("tasks")
    Task.set_db(d)
    return s,d

class Task(Document):
    id = StringProperty()
    summary = StringProperty()
    content = StringProperty()

    creator = StringProperty()
    assignee = StringProperty()
    created_at = DateTimeProperty()

    def save(self,user=None,notify=True):
        try:
            Document.save(self)
        except:
            print 'could not save task %s'%self._id
            raise
        if not notify: return
        if notify:
            import tasks
            tasks.notifications.apply_async((user,self._id),countdown=5)
        
    def _notify(self,user):
        print 'in notify'
        import sendgrid
        from docs import D,get_participants
        participants = get_participants(disabled=True)
        lc = last_change(self,D)
        if not lc: return
        rev,html,text,changes = lc
        if not hasattr(self,'notifications'): self.notifications={}
        if rev in self.notifications: return
        import config as cfg
        sg = sendgrid.SendGridClient(cfg.SENDGRID_USERNAME,cfg.SENDGRID_PASSWORD,secure=True)
        subj = '%s - %s ch.'%(self._id,','.join(changes))+(user and ' by %s'%user or '')
        snd = cfg.SENDER
        rcpts = set(self.informed+[self.creator,self.assignee] )-(user and set([user]) or set())
        rems = [participants[r]['E-Mail'] for r in rcpts]
        to = ', '.join(rems)
        print 'sending mail to %s'%to
        for rcpt in rems:
            msg = sendgrid.Mail(to=rcpt,
                                subject = subj,
                                html=html,
                                text=text,
                                from_email=snd)

            status,res = sg.send(msg)
            assert status==200,Exception(status,res)
        notif = {'notified_at':datetime.datetime.now(),
                 'user':user,
                 'informed':rcpts}
        self.notifications[rev]=notif
        print 'saving notification'
        self.save(user='notify-trigger',notify=False)
        print 'done'

        
def push_views(d):
    # from couchdbkit.loaders import FileSystemDocsLoader
    # loader = FileSystemDocsLoader('couchdb/_design/task')
    # loader.sync(d,verbose=True)
    print 'pushing views'
    push('couchdb/_design/task',d,force=True)

################################################################################
from json import dumps, loads, JSONEncoder, JSONDecoder
import pickle
import datetime

class PythonObjectEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (list, dict, str, unicode, int, float, bool, type(None))):
            return JSONEncoder.default(self, obj)
        elif isinstance(obj,(datetime.datetime)):
            return obj.strftime('%Y-%m-%d')
        return {'_python_object': pickle.dumps(obj)}

def as_python_object(dct):
    if '_python_object' in dct:
        return pickle.loads(str(dct['_python_object']))
    return dct
################################################################################

def get_all():
    return Task.view('task/all')

def get_task(tid):
    return Task.get(tid)

def get_children(tid):

    ints = [int(tp) for tp in tid.split('/')]

    sk = ints
    ek = ints+[{}]
    tasks = Task.view('task/children',
                      startkey=sk,
                      endkey=ek,
    )
    rt= [t for t in tasks if t._id!=tid]
    return rt

def get_parents(tid):
    ints = [int(tp) for tp in tid.split('/')]
    keys=[]
    for l in range(1,len(ints)):
        keys.append(ints[0:l])    
    tasks = Task.view('task/children',
                      keys=keys)
    return tasks

def get_by_tag(tag):
    return Task.view('task/tags',key=tag)

def get_related(rel):
    return Task.view('task/related',key=rel)

def get_by_status(st):
    return Task.view('task/status',key=st)

def get_ids():
    ids = Task.view('task/ids')
    return [r['id'] for r in ids]

def get_new_idx(par=''):
    #print 'getting new idx %s'%par
    par = str(par)
    allids = get_ids()
    agg={}
    for tid in allids:
        pth = tid.split('/')
        val = pth[-1]
        aggk = '/'.join(map(lambda x:str(x),pth[0:-1]))
        if aggk not in agg: agg[aggk]=0
        if int(agg[aggk])<int(val): agg[aggk]=val
        if tid not in aggk: agg[tid]=0
    #raise Exception(agg)
    assert par in agg,"%s not in agg %s"%(par,agg.keys())
    print 'returning %s + / + %s'%(par,int(agg[par])+1)
    print 'par = "%s" ; agg[par] = "%s"'%(par,agg[par])
    rt= (par and str(par)+'/'or '')+str(int(agg[par])+1)
    return rt

def get_journals():
    return Task.view('task/journals')

def get_tags():
    tags = [t['key'] for t in Task.view('task/tag_ids')]
    agg={}
    for t in tags:
        if t not in agg: agg[t]=0
        agg[t]+=1
    return agg

def last_change(t,d,specific_rev=None):
    import json
    import difflib
    doc = d.open_doc(t._id,revs=True)
    #print '<h1>current rev',t._rev+'</h1>'
    #print '<p>previous revs',doc['_revisions']['ids'],'</p>'
    i=len(doc['_revisions']['ids'])
    pdc={} ; prev = None
    #print '<pre>',json.dumps(dict(t),indent=True,cls=PythonObjectEncoder),'</pre>'
    for rev in doc['_revisions']['ids']:
        obt = '%s-%s'%(i,rev)
        if specific_rev and specific_rev not in [prev,obt]:
            continue
        #print '<h2>obtaining',obt,'</h2>'
        t2 = Task.get(t._id,rev=obt)
        dc = dict(t2)

        if pdc and pdc!=dc:
            rt= '<h4>diff between %s and %s</h4>'%(obt,prev)
            changes=[]
            comparison = compare(pdc,dc)
            for cd in comparison:
                msg = cd['message']
                found=False
                for k in ['branch','details','journal','status','assignee','summary','tags','informed','unstructured']:
                    if msg.startswith(k): 
                        changes.append(k)
                        found=True
                        break
                if not found: 
                    print 'unknown change %s'%cd
                    changes.append('unkn')

            j2 = json.dumps(pdc,indent=True,cls=PythonObjectEncoder,sort_keys=True)
            j1 = json.dumps(dc,indent=True,cls=PythonObjectEncoder,sort_keys=True)
            #print '<pre>'+j1+'</pre>'
            rt+= difflib.HtmlDiff().make_file(j1.split("\n"),j2.split("\n"),context=True)
            textdiff = difflib.ndiff(j1.split("\n"),j2.split("\n"))
            changes.sort()
            return prev,rt,textdiff,set(changes)
        pdc = dc ; prev = obt
        i-=1
        #pprint.pprint( dict(t2))
    return None
