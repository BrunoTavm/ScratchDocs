import datetime

from docs_old import get_fns,initvars,get_task,parse_fn,read_journal
from couchdbkit.exceptions import ResourceNotFound
import config as cfg    
import sys
import json
initvars(cfg)

from couchdb import Task,init_conn


impkeys = ['status', 
           u'assigned to', 
           'story', 
           'tags', 
           u'created at',
           u'informed',
           u'assigned to',
           u'created at',
           'summary',
           'unstructured',
           'jpath',
           u'points',
           'meta',
           u'created by',
           u'created by ',
           u'points ',
           'path',
           'id',
           'metadata']

def ask(o,k,defv=-1):
    if defv!=-1 and k not in o:
        return defv
    if k not in o:
        raise Exception('%s not present in %s'%(k,o))
    rt = o[k]
    del o[k]
    return rt

def imp():
    for tfn,tid in [(tf,parse_fn(tf)['id']) for tf in get_fns()]:
        print tid

        #handle task
        t= get_task(tid,read=True)
        notifications = ask(t['meta'],'notifications',[]) #throw away, for now
        points = ask(t,'points',None) # throw away
        branches = ask(t['meta'],'branches',None) # throw away
        status = ask(t,'status')
        repobranch = ask(t,'repobranch',[])
        links = ask(t,'links',[])
        assignee = ask(t,'assigned to')
        creator = ask(t,'created by')
        summary = ask(t,'summary')
        created_at = ask(t,'created at')
        tags = ask(t,'tags')
        informed = ask(t,'informed',None)
        unstructured = ask(t,'unstructured')
        try:
            unstructured = unicode(unstructured,'utf-8')
        except:
            print type(unstructured),unstructured,'"%s"'%unstructured[10:15]
            raise
        try:
            td = Task.get(tid)
            if td: td.delete()
        except ResourceNotFound:
            pass

        td = Task(_id=tid,
                  path=[int(tp) for tp in tid.split('/')],

                  created_at=created_at,
                  summary=summary,

                  status=status,

                  creator=creator,
                  assignee=assignee,
                  informed=informed,

                  links=links,
                  branches=repobranch,
                  tags=tags,

                  unstructured=unstructured
        )

        #delete ignored meta keys
        for dk in ['commits_qty','branchlastcommits','lastcommits','commiters','last_commit']:
            if dk in t['meta']:
                del t['meta'][dk]

        #assert bogus keys are empty
        for ek in ['meta','created by ','points ','points','assigned to ','created at ','meta']:
            if ek in t:
                assert (not t[ek] or t[ek]=='None'),"%s = %s"%(ek,t[ek])
                del t[ek]
        #delete ignored keys 
        for dk in ['story','jpath','path','id','metadata']:
            del t[dk]
        if len(t):
            print dumps(t,indent=True,cls=PythonObjectEncoder);    sys.exit(1)

        #handle journal
        jfn = tfn.replace('task.org','journal.org')
        j = read_journal(jfn)
        #ignored keys
        print len(j),'journal entries'
        je = []
        for i in j:
            creator = ask(i,'creator')
            content = ask(i,'content')
            attrs = ask(i,'attrs')
            created_at = ask(i,'created at')
            assert i['tid']==tid
            for dk in ['rendered_content','tid']:
                del i[dk]
            if len(i):
                print dumps(j,indent=True,cls=PythonObjectEncoder);    sys.exit(1)

            je.append({'creator':creator,
                       'content':content,
                       'attrs':attrs,
                       'created_at':created_at})
        td.journal = je
        td.save(notify=False,user='couchdb_import')

if __name__=='__main__':
    s,d = init_conn()
    imp()

