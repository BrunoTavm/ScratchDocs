#!/usr/bin/env python
import argparse
import config as cfg
from commands import getstatusoutput as gso
from prettytable import PrettyTable
import os
from mako.template import Template

parser = argparse.ArgumentParser(description='Task Control',prog='tasks.py')
subparsers = parser.add_subparsers(dest='command')

list = subparsers.add_parser('list')
list.add_argument('--teration',dest='iteration')

gen = subparsers.add_parser('generate')

args = parser.parse_args()

def parse_story_fn(fn):
    parts = fn.replace(cfg.DATADIR,'').split('/')
    it = parts[1]
    story = '/'.join(parts[2:-1])
    return {'iteration':it,'story':story}

def get_task_files(iteration=None):
    if iteration:
        itcnd=' -wholename "%s*"'%(os.path.join(cfg.DATADIR,str(iteration)))
    else:
        itcnd=''
    cmd = "find %s %s -type f -name 'index.org'"%(cfg.DATADIR,itcnd)
    st,op = gso(cmd) ;assert st==0,"%s => %s"%(cmd,op)
    files = op.split('\n')
    return files

def sort_iterations(i1,i2):
    try:i1v = int(i1[0])
    except ValueError: i1v = 1000
    try: i2v = int(i2[0])
    except ValueError: i2v = 1000
        
    rt= cmp(i1v,i2v)
    return rt
def get_iterations():
    cmd = 'find %s  -maxdepth 1 -type d'%(cfg.DATADIR)
    st,op = gso(cmd) ; assert st==0
    #print op  ; raise Exception('w00t')
    dirs = op.split('\n')
    rt = [(os.path.basename(path),path) for path in dirs if len(path.split('/'))>1]
    rt.sort(sort_iterations,reverse=True)
    return rt
def list_stories(iteration=None):
    files = get_task_files(iteration=iteration)

    pt = PrettyTable(['iteration','id'])
    cnt=0
    for fn in files:
        sd = parse_story_fn(fn)
        if iteration and sd['iteration']!=str(iteration): continue
        pt.add_row([sd['iteration'],sd['story']])
        cnt+=1
    print pt
    print '%s stories.'%cnt
if args.command=='list':
    list_stories(iteration=args.iteration)
if args.command=='generate':
    iterations = get_iterations()
    tpl = Template(open('templates/iterations.org').read())
    vardict = {'iterations':iterations}
    itlist = tpl.render(**vardict)
    fp = open(os.path.join(cfg.DATADIR,'index.org'),'w') ; fp.write(itlist) ; fp.close()

    sttpl = Template(open('templates/stories.org').read())
    for it in iterations:
        print 'walking iteration %s'%it[0]
        taskfiles = get_task_files(iteration=it[0])
        stories = [(fn,parse_story_fn(fn)) for fn in taskfiles]
        vardict = {'iteration':it,'stories':stories}
        stlist = sttpl.render(**vardict)
        itidxfn = os.path.join(cfg.DATADIR,it[0],'index.org')
        fp = open(itidxfn,'w') ; fp.write(stlist) ; fp.close()
