# coding: utf-8
#

from tornado.web import authenticated
from rethinkdb import r

from ..database import db, time_now
from .base import AuthRequestHandler, AdminRequestHandler


import jenkins

class AgentsListHandler(AuthRequestHandler):
    def get(self):
        self.render('agents.html') 


class APIAgentHandler(AuthRequestHandler):
    async def get(self):
        agents = await db.table('agents').filter({}).all()
        self.write_json({
            "sucess":True,
            'agents':agents
            })
    
    async def post(self):
        import uuid

        name = self.get_argument('name', None)
        token = self.get_argument('token', None)
        addr = self.get_argument('addr', None)
        num  = self.get_argument('execute_num', 1)
        device  = self.get_argument('device', 1)
        desc = self.get_argument('desc', '')
        aid = self.get_argument('aid', None)
        
        launch_params = self.get_argument('launch_params', '')
        
        if not name or not token or not device:
            raise Exception('参数错误')
        
        data = {
            "name": name,
            "token": token,
            "addr":addr,
            "device": device,
            'execute_num':num,
            'desc':desc,
            "launch_params": launch_params
        }
        
        agents = await db.table('agents').filter({'device': device}).all()
        print(agents)
        if len(agents)>0:
            data.pop('device')
            ret = await db.table('agents').filter({'device': device}).update(data)
            # self.write_json({
            #     'success':True,
            #     'msg':'agent已存在'
            #     })
            # return
        
        elif aid:
            ret = await db.table('agents').filter({'aid':aid}).update(data)
            self.write_json({
                    'success':True,
                    'data':ret
                    })
        else:
            data['aid'] = str(uuid.uuid1())
            ret = await db.table("agents").save(data)
            
            
        import jenkins
        node_name = f'Node_{name}'
        print([addr, name , token])
        j = jenkins.Jenkins(addr,username=name,password=token)
        print(j)
        if not j.node_exists(node_name):
            j.create_node(node_name)
            info = j.get_node_info(node_name)
            print(info)
            self.write_json({
                'success': True,                
                'data': {
                    'db':ret,
                    'node':info
                }
            })
    
    async def delete(self):
        aid = self.get_argument('aid', None)
        print('del: '+ aid)
        ret = await db.table('agents').filter({'aid':aid}).delete()
        print(ret)
        self.write_json({
            'success': True,
            'data': ret
            })