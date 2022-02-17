# coding: utf-8
#

from tornado.web import authenticated
from rethinkdb import r
from logzero import logger
from six.moves.urllib.parse import urlencode

from ..database import db, time_now
from .base import AuthRequestHandler, AdminRequestHandler

import os,requests,re
import jenkins
from jenkinsapi.jenkins import Jenkins

jenkins_url   = os.environ.get('AT_JENKINS_URL','http://172.16.246.89:8080/')
jenkins_name = os.environ.get('AT_JENKINS_NAME','wh.huang@tuya.com')
jenkins_token = os.environ.get('AT_JENKINS_TOKEN','11992db19960280f1213ccb39ad9d0ee15')


def _compress_and_lower(value):
    value = value.replace(' ','')
    return value.lower()

def allParms_from_request(request):
    '''
    从request中获取所有参数
    '''
    post_data = request.arguments
    post_data = {
        x: post_data.get(x)[0].decode("utf-8") for x in post_data.keys()}
    if not post_data:
        post_data = self.request.body.decode('utf-8')
        post_data = json.loads(post_data)
    print(post_data)
    return post_data

def get_token_forurl(url):
    import re
    auth = requests.auth.HTTPBasicAuth(jenkins_name.encode('utf-8'), jenkins_token.encode('utf-8'))
    res = requests.get(url,auth = auth)
    m = re.findall(r'(?<=<argument>)[a-z0-9]{64}(?=</argument>)',res.text) 
    if m:
        logger.debug(m)
        return m[0]

class TJenkins(object):
    def __init__(self):
        self.japi : Jenkins = Jenkins(jenkins_url,username=jenkins_name,password=jenkins_token,lazy=True)
        pass
    
    async def create(self,nodename,labels=[],**kwargs):
        node_dict = {
            'num_executors': 1,
            'node_description': kwargs.pop('desc'),
            'remote_fs': nodename,
            'labels': ' '.join(labels),
            'exclusive': True
        }
        node_dict.update(kwargs)
        # 使用jenkinsapi创建node， 使用 jenkins 创建是会失败
        logger.info(node_dict)
        
        
        
        if self.japi.has_node(nodename):
            J = jenkins.Jenkins(jenkins_url,username=jenkins_name,password=jenkins_token)
            xml = J.get_node_config(nodename)
            logger.info(xml)
            xml = re.sub(r'(?<=<label>).+(?=</label>)', node_dict['labels'],xml)
            logger.info(xml)
            xml = re.sub(r'(?<=<description>).+(?=</description>)', node_dict.pop('node_description'),xml)
            logger.info(xml)
            J.reconfig_node(nodename, xml)
        else:
            from jenkinsapi import node
            node = node.Node(self.japi.get_jenkins_obj(),None, nodename=nodename, node_dict= node_dict)
            config = node.get_node_attributes()
            logger.info(config)
            self.japi.create_node_with_config(nodename,config=config)
        
        token = self.fetch_token(nodename)
        await db.table("agents").filter({'name':nodename}).update({'token':token,'labels':node_dict['labels']})
    
    def fetch_token(self,nodename) -> str:
        url = self.japi.get_node_url(nodename) + '/jenkins-agent.jnlp'
        res = self.japi.requester.get_and_confirm_status(url,)
        logger.info(res)
        token = get_token_forurl(url)
        return token
    
class APIJenkinsHandler(AuthRequestHandler):
    async def post(self):
        post_data = allParms_from_request(self.request)
        udid = post_data['udid']
        
        agent =  await db.table("agents").get(udid).run()
        device =  await db.table("devices").get(udid).run()
        device_properties = device['properties']
        
        platform = device['platform']
        brand = device_properties['brand']
        version = device_properties['version'] if 'version' in device_properties else None
        
        labels = []
        labels.append(_compress_and_lower(platform))
        labels.append(udid)
        labels.append(_compress_and_lower(brand))
        if version:
            os = ''
            for v in str(version).split('.'):
                if len(os) >0 :
                    os = os + '.'
                os += v
                labels.append('os{}'.format(os))
        if 'tags' in agent:
            labels.extend(agent['tags'].split(' '))
        await TJenkins().create(agent['name'],labels=labels,desc=agent['desc'],env=[{'key':"DEVICE_ID",'value':udid}])
        
        self.write_json({
            'success':True,
            'data':None
            })
        
class AgentsListHandler(AuthRequestHandler):
    def get(self):
        self.render('agents.html') 

class APIAgentHandler(AuthRequestHandler):
    async def get(self):
        agents = await db.table('agents').filter({}).all()
        self.write_json({
            "success":True,
            'agents':agents
            })
    
    async def post(self):
        logger.info('新建')
        import uuid

        post_data = self.request.arguments
        post_data = {
            x: post_data.get(x)[0].decode("utf-8") for x in post_data.keys()}
        if not post_data:
            post_data = self.request.body.decode('utf-8')
            post_data = json.loads(post_data)
        logger.info(post_data)
        
        udid = post_data['udid']
        
        if not udid:
            raise Exception('参数错误')    
    
        # device
        d = await db.table("devices").get(udid).run()
        node_name = 'AT_{}_{}'.format(d['platform'].upper() ,d['udid'][0:6].upper()) 
        post_data['name'] = node_name
        
        agents = await db.table('agents').filter({'udid': udid}).all()
        if len(agents)>0:
            self.write_json({
                'success':False,
                'msg': f'{udid} existed'
                })
            return
        
        ret = await db.table("agents").save(post_data)
        self.write_json({
            "success":True,
            'data':ret
            })
            
    
    async def put(self):
        print('update agent')
        post_data = self.request.arguments
        post_data = {
            x: post_data.get(x)[0].decode("utf-8") for x in post_data.keys()}
        if not post_data:
            post_data = self.request.body.decode('utf-8')
            post_data = json.loads(post_data)
        logger.info(post_data)
        
        udid = post_data.pop('udid')
        assert(udid is not None)
        
        d = await db.table("devices").get(udid).run()
        post_data['name'] = 'AT_{}_{}'.format(d['platform'].upper() ,d['udid'][0:6].upper()) 
            
        
        ret = await db.table('agents').get(udid).update(post_data)
        self.write_json({
            'success': True,
            'data': ret
            })
        
        
    async def delete(self):
        udid = self.get_argument('udid', None)
        print('del: '+ udid)
        ret = await db.table('agents').filter({'udid':udid}).delete()
        print(ret)
        self.write_json({
            'success': True,
            'data': ret
            })