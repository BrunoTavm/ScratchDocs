#!/usr/bin/env python
import cProfile,pstats
import config as cfg
import tasks
from tasks import parse_story_fn as parse_fn
from tasks import get_task_files as get_fns
tasks.initvars(cfg)
def run():
    in_tasks = [tasks.parse_story_fn(fn,read=True,known_iteration='42') for fn in tasks.get_task_files(assignee=None,iteration='42',recurse=False)]
cProfile.run('run()','profile.log')
s = pstats.Stats('profile.log')
s.strip_dirs().sort_stats('cumulative').print_stats(30)
#run()
