#!/usr/bin/env python
import MySQLdb as my
import prettytable
import config as cfg
import codecs
import os
from mako.template import Template
from docs import get_task,render
import sys

usermap = {'andysnagovsky':'andrey_s',
           'milez':'guy',
           'nskrypnik':'nikolay_s',
           'dkhinoy':'denis_k',
           '3demax':'maxim_g',
           'zyko':'denis_d',
           'romepartners':'lillian',
           'lillian':'lillian',
           'dima':'dmitry_m',
           'serg0987':'sergey_g',
           'dimonji':'dmitry_f',
           'notreserved':'eugene_c',
           'checha':'andrey_c',
           'borist':'boris_t',
           'denis_d':'denis_d',
           'vitaly_shcherbak':'vitaly_s',
           'HFlamov':'maxim_d',
           'anna_kukoyashnaya':'anna_k',
           '4031651':'sergey_t',
           'vjacheslaw_b':'vjacheslaw_b',
           'yraksenov':'yury_a',
           'Flamov':'maxim_d',
           'igor':'igor_y',
           'artem_p':'artem_p',
           'Rinat':'rinat_i',
           'jazz':'andrey_n',
           'singleplayer':'kathrin_s',
           'ester_s':'ester_s',
           'slava_l':'slava_l',
           'shatunov_sv':'sergey_s',
           'sergey_p':'sergey_p',
           'vladimir_b':'vlarimir_b',
           'alex_y':'alex_y',
           'nadezhda_r':'nadezhda_r',
           'eliah_l':'eliah_l'
        }
statuses = {1:'TODO',
            2:'DOING',
            3:'REVIEW',
            4:'DONE'}

db = my.connect(host='localhost',user='root',db='backlog')
c = db.cursor() #cursorclass=my.cursors.CursorTupleRowsMixIn())
c2 = db.cursor()
c3 = db.cursor()
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

    #fetch comments
    c3.execute("select a.username,c.comment,c.date_submitted from threadedcomments_threadedcomment c left outer join auth_user a on c.user_id=a.id where object_id=%d"%(r['id']))
    storycomments=[]
    while True:
        trow = c3.fetchone()
        if not trow: break
        un,comment,dt = trow
        comment = comment.replace('\n','')
        if 'commited to github' in comment: continue
        try:
            unicode(comment)
        except:
            try:
                comment = comment.decode('utf-8')
            except:
                comment = comment.decode('cp1251')

        storycomments.append({'username':usermap[un],'comment':comment,'date':dt})
    def ssrt(s1,s2):
        return cmp(s1['date'],s2['date'])
    storycomments.sort(ssrt)
    r['comments']=storycomments
    #fetch tasks
    c3.execute("select t.summary,t.complete,a.username from projects_task t left outer join auth_user a on a.id=t.assignee_id where story_id=%d"%r['id'])
    ptasks=[]
    while True:
        trow = c3.fetchone()
        if not trow: break
        tsum,tcomplete,tassignee = trow
        ptasks.append({'summary':tsum,'complete':tcomplete,'assignee':(tassignee and usermap[tassignee] or None)})
    r['stasks']=ptasks

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
    storyfn = os.path.join(storydir,cfg.TASKFN)
    storycont = render('task',r,storyfn)
    cnt+=1
print pt
print '%s stories counted.'%cnt
