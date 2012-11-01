import MySQLdb as my
import prettytable
import config as cfg
import codecs
import os
from mako.template import Template

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

itertpl = Template(open('templates/iteration.org').read())

tpl = Template(open('templates/task.org').read())

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

    iterdir = os.path.join(cfg.DATADIR,r['iteration'])
    if not os.path.exists(iterdir): os.mkdir(iterdir)

    iterfn = os.path.join(iterdir,'iteration.org')
    if not os.path.exists(iterfn):
        itercont = itertpl.render(**iterinfo[r['iteration']])
        fp = open(iterfn,'w'); fp.write(itercont); fp.close()

    assert r['story_id']
    storydir = os.path.join(iterdir,str(r['story_id']))

    if not os.path.exists(storydir): os.mkdir(storydir)
    print 'rendering story %s'%r['story_id']
    try:
        r['detail'] = r['detail'].decode('utf-8')
        #raise Exception(type(r['detail']))
    except UnicodeDecodeError:
        r['detail']= r['detail'].decode('cp1251')
    #r['detail'] = r['detail'].decode('utf-8')
    storycont = tpl.render(**r)
    storyfn = os.path.join(storydir,cfg.TASKFN)
    fp = codecs.open (storyfn,'w','utf-8')
    fp.write(storycont)
    fp.close()
    #pt.add_row(row)
    cnt+=1
print pt
print '%s stories counted.'%cnt
