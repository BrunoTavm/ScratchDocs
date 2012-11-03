#!/usr/bin/env python
import MySQLdb as my
import prettytable
import config as cfg
import codecs
import os
from mako.template import Template
from tasks import get_task,render
import sys

usermap = {'andysnagovsky':'andrey.s',
           'milez':'guy',
           'nskrypnik':'nikolay.s',
           'dkhinoy':'denis.k',
           '3demax':'maxim.g',
           'zyko':'denis.d',
           'romepartners':'lillian',
           'dima':'dmitry.m',
           'serg0987':'sergey.g',
           'dimonji':'dmitry.f',
           'notreserved':'eugene.c',
           'checha':'andrey.c',
           'borist':'boris.t',
           'denis_d':'denis.d',
           'vitaly_shcherbak':'vitaly.s',
           'HFlamov':'maxim.d',
           'anna_kukoyashnaya':'anna.k',
           '4031651':'sergey.t',
           'vjacheslaw_b':'vjacheslaw_b',
           'yraksenov':'yury.a',
           'Flamov':'maxim.d',
           'igor':'igor.y',
           'artem_p':'artem.p',
           'Rinat':'rinat.i',
           'jazz':'andrey.n',
           'singleplayer':'kathrin.s',
           'ester_s':'ester.s',
           'slava_l':'slava.l',
           'shatunov_sv':'sergey.s',
           'sergey_p':'sergey.p',
           'vladimir_b':'vlarimir.b',
           'alex_y':'alex.y',
           'nadezhda_r':'nadezhda.r',
           'eliah_l':'eliah.l'
        }
statuses = {1:'TODO',
            2:'DOING',
            3:'REVIEW',
            4:'DONE'}

db = my.connect(host='localhost',user='root',db='backlog')
c = db.cursor() #cursorclass=my.cursors.CursorTupleRowsMixIn())
c2 = db.cursor()
c.execute("""select * from projects_iteration where project_id=1""")
d={}
for i in range(len(c.description)):
    d[i]=c.description[i][0]
iterinfo={}
while True:
    row = c.fetchone()
    if not row: break
    r = dict([(d[i],row[i]) for i in range(len(row))])
    iterinfo[r['name']]=r


c.execute("""select 
s.id,
i.name as iteration,
s.local_id as story_id,
s.created,
c.username as creator,
a.username as assignee,
s.summary,
s.detail,
s.status,
s.points
from 
projects_story s
-- ,projects_iteration i 
LEFT OUTER JOIN auth_user a ON s.assignee_id=a.id
LEFT OUTER JOIN auth_user c ON s.creator_id=c.id
LEFT OUTER JOIN projects_iteration i ON s.iteration_id=i.id
where 
s.project_id=1
-- AND s.iteration_id=i.id
""")
d={}
for i in range(len(c.description)):
    d[i]=c.description[i][0]



pt = prettytable.PrettyTable(d.values())
cnt=0
while True:
    row = c.fetchone()
    if not row: break
    r = dict([(d[i],row[i]) for i in range(len(row))])
    for fn in ['assignee','creator']:
        if r[fn] and r[fn] in usermap:
            r[fn]=usermap[r[fn]]
        elif r[fn] and '.' not in r[fn]: raise Exception(r[fn])
    r['status']=statuses[r['status']]

    #fetch tags
    storytags=[]
    c2.execute("select name from projects_storytag where project_id=1 and id in (select tag_id from projects_storytagging where story_id=%d)"%(r['id']))
    while True:
        trow = c2.fetchone()
        if not trow: break
        tag = trow[0]
        if 'pivotal' in tag: continue
        if tag not in storytags: storytags.append(tag)

    iterdir = os.path.join(cfg.DATADIR,r['iteration'])
    if not os.path.exists(iterdir): os.mkdir(iterdir)

    iterfn = os.path.join(iterdir,'iteration.org')
    render('iteration',iterinfo[r['iteration']],iterfn)

    assert r['story_id']
    #make sure we are not overwriting
    if 'force' not in sys.argv:
        t = get_task(r['story_id'],exc=False)
        if t:
            continue
    storydir = os.path.join(iterdir,str(r['story_id']))

    if not os.path.exists(storydir): os.mkdir(storydir)
    print 'rendering story %s'%r['story_id']
    try:
        r['detail'] = r['detail'].decode('utf-8')
        #raise Exception(type(r['detail']))
    except UnicodeDecodeError:
        r['detail']= r['detail'].decode('cp1251')
    r['tags']=storytags
    #r['detail'] = r['detail'].decode('utf-8')
    storycont = render('task',r,storyfn)
    cnt+=1
print pt
print '%s stories counted.'%cnt
