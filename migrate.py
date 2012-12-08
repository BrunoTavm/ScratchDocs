import os
from commands import getstatusoutput as gso
assert os.path.exists('t')
assert os.path.exists('i')

st,op = gso('find ./ -type f -name "task.org" ! -wholename "./sd*"') ; assert st==0
files = op.split('\n')
#we sort by reverse depth in order to move the deepest ones first.
files.sort(lambda f1,f2: cmp(len(f1.split('/')),len(f2.split('/'))),reverse=True)
#print [len(f.split('/')) for f in files]
for fn in files:
    sdir = os.path.dirname(fn)
    parts = sdir.split('/')
    tid = '/'.join(parts[2:])
    itn = parts[1]

    print '########## %s ##########'%(tid)
    tdir = os.path.join('t',tid)
    itlnk = os.path.join('i',itn,tid)
    #print '%s goes to %s ; symlink in %s'%(fn,tdir,itlnk)
    #assert not os.path.exists(tdir),"%s already there!"%(tdir)

    #start shufflin'
    mkdirp = 'mkdir -p %s'%tdir
    print mkdirp
    st,op = gso(mkdirp)
    taskfilesf = 'find %s -maxdepth 1 -type f'%(sdir)
    print taskfilesf
    st,op =gso(taskfilesf) ; assert st==0
    taskfiles = [tf for tf in op.split('\n') if tf!='']
    #print taskfiles
    for f in taskfiles:
        dfile = os.path.join(tdir,os.path.basename(f))
        assert not os.path.exists(dfile),"destination file %s exists"%(dfile)
        fmvcmd = 'cp %s %s'%(f,dfile)
        print fmvcmd
        st,op = gso(fmvcmd) ; assert st==0
    itdir = os.path.join('i',itn)
    if not os.path.exists(itdir):
        os.mkdir(itdir)
        itcp = 'cp %s %s'%(os.path.join(itn,'iteration.org'),os.path.join('i',itn))
        print itcp
        st,op = gso(itcp) ; assert st==0
    lncmd = 'ln -s %s "%s"'%('../../t/'+tid,os.path.join(itdir,('.'.join(parts[2:]))))
    print lncmd
    st,op = gso(lncmd) ; assert st==0


