from commands import getstatusoutput as gso
from orm import *
import re
import os
import sys
import datetime
from dulwich.repo import Repo as DRepo
import config as cfg
def import_commits(fetch=True):
    st,op = gso('which git-new-workdir') ; assert st==0
    cachedir = '~/Projects/scratch-repos-cache'
    taskre = re.compile('\#([\d\/]+)')
    mydir = cfg.REPO_DIR
    assert os.path.exists(mydir),mydir
    rc={} #cache
    repos = s.query(Repo).all()
    from tasks import get_table_contents

    repos = [r['Name'] for r in get_table_contents('repos.org')]
    for rname in repos:
        print 'doing repo %s'%rname
        rdir = os.path.join(mydir,rname)
        if not os.path.exists(rdir):
            gnwdcmd = 'git-new-workdir %s %s'%(os.path.join(cachedir,rname),
                                                 rdir)
            st,op = gso(gnwdcmd)
            assert st==0,gnwdcmd
        if fetch:
            st,op = gso('cd %s && git fetch -a'%rdir) ; assert st==0

        st,op = gso('cd %s && git rev-list --since=2013-06-01 --remotes'%rdir); 
        assert st==0
        for revid in [rid for rid in op.split('\n') if len(rid)]:
            cm = s.query(Commit).\
                filter(Commit.repo==rname).\
                filter(Commit.rev==revid).first()
            if cm: continue
            if rdir not in rc:
                rc[rdir] = DRepo(rdir)
            dr = rc[rdir]
            assert revid
            o = dr.get_object(revid)

            taskres = taskre.search(o.message.strip())
            if taskres: task = taskres.group(1)
            else: task = None



            cm = Commit()
            cm.repo = rname
            cm.rev = revid
            #cm.author = o.author
            author_res = re.compile('(?P<name>.+) <(?P<email>.+)>$').search(o.author)
            assert author_res,o.author
            author_name,author_email =            author_res.groups()

            from commiters_map import EMAIL_MAP
            if author_email in EMAIL_MAP.values():
                cm.author = author_email
            else:
                for rg,to in EMAIL_MAP.items():
                    if rg.search(author_email):
                        cm.author = to
                        break
            assert cm.author,o.author

            cm.message = o.message.strip()
            cm.task = task
            cm.commited_on = datetime.datetime.fromtimestamp(o.commit_time)
            cm.size = o.raw_length()
            s.add(cm) ; s.commit()
