#!/usr/bin/env python
import unittest
import config_test as cfg
import tasks
import os
from commands import getstatusoutput as gso 
class TestTask(unittest.TestCase):
    def __init__(self,tc):
        tasks.initvars(cfg)
        if not os.path.exists(cfg.DATADIR): os.mkdir(cfg.DATADIR)
        st,op = gso('rm -rf %s/*'%cfg.DATADIR) ; assert st==0
        os.mkdir(os.path.join(cfg.DATADIR,'t'))
        os.mkdir(os.path.join(cfg.DATADIR,'i'))
        unittest.TestCase.__init__(self,tc)
    def test_iteration_creation(self):
        tasks.add_iteration('testiter')
        rt = tasks.add_task('testiter',parent=None,params={'summary':'1st test task'},tags=['chuckacha'])
        tf = tasks.get_task_files(iteration='testiter',flush=True)
        assert len(tf)==1
        for i in range(5):
            rt2 = tasks.add_task(iteration=None,parent=rt['id'],params={'summary':'1st subtask'},tags=['subtask'])
            #print rt2
            tf = tasks.get_task_files(iteration='testiter',recurse=True,flush=True)
            assert len(tf)==i+2
        tf = tasks.get_task_files(iteration='testiter',recurse=False,flush=True)
        assert(len(tf)==1),"%s even though recurse=False"%tf
        t1 = tasks.get_task(rt['id'],read=True)
        assert t1['id']==rt['id']
        assert t1['summary']=='1st test task'
        assert 'chuckacha' in t1['tags']
        t2 = tasks.get_task(rt2['id'],read=True)
        assert t2['summary']=='1st subtask'
        assert 'subtask' in t2['tags']
        tasks.add_iteration('iter2')
        tasks.move_task(t2['id'],'iter2')
        mt = tasks.get_task(t2['id'],flush=True)
        assert mt['iteration']=='iter2',mt
        tasks.tasks_validate(tasks=[],exc=True)
    def setUp(self):
        pass
if __name__=='__main__':
    unittest.main()
