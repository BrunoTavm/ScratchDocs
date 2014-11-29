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
    print 'pushing views'
    push('couchdb/_design/task',d)

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
