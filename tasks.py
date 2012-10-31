#!/usr/bin/env python
import argparse
import config as cfg
from commands import getstatusoutput as gso
from prettytable import PrettyTable

parser = argparse.ArgumentParser(description='Task Control',prog='tasks.py')
list = parser.add_argument_group('List','Browse stories by various criterea')
list.add_argument('list', nargs="+", metavar='list')
args = parser.parse_args()

def parse_fn(fn):
    parts = fn.replace(cfg.DATADIR,'').split('/')
    it = parts[1]
    story = '/'.join(parts[2:-1])
    return {'iteration':it,'story':story}
def list_stories(iteration=None):
    st,op = gso("find %s -type f -name 'task.org'"%cfg.DATADIR) ;assert st==0
    files = op.split('\n')
    pt = PrettyTable(['iteration','id'])
    for fn in files:
        sd = parse_fn(fn)
        if str(iteration) and sd['iteration']!=str(iteration): continue
        pt.add_row([sd['iteration'],sd['story']])
    print pt

if args.list:
    list_stories(iteration=40)
