from couchdbkit import *

def init_conn():
    #print 'creating server'
    s = Server()
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


def push_views(d):
    # from couchdbkit.loaders import FileSystemDocsLoader
    # loader = FileSystemDocsLoader('couchdb/_design/task')
    # loader.sync(d,verbose=True)
    print 'pushing views'
    push('couchdb/_design/task',d,force=True)

################################################################################
from json import dumps, loads, JSONEncoder, JSONDecoder
import pickle

class PythonObjectEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (list, dict, str, unicode, int, float, bool, type(None))):
            return JSONEncoder.default(self, obj)
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
                      group=False
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
    return [r['key'] for r in Task.view('task/ids')]

def get_new_idx(par=''):
    par = str(par)
    allids = get_ids()
    agg={}
    for pth in allidsnewidx:
        val = pth[-1]
        aggk = '/'.join(map(lambda x:str(x),pth[0:-1]))
        if aggk not in agg: agg[aggk]=-1
        if agg[aggk]<val: agg[aggk]=val
    print par in agg
    return par+'/'+str(agg[par]+1)

def get_journals():
    return Task.view('task/journals')

def get_tags():
    tags = [t['key'] for t in Task.view('task/tag_ids')]
    agg={}
    for t in tags:
        if t not in agg: agg[t]=0
        agg[t]+=1
    return agg
