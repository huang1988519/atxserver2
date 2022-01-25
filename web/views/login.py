# coding: utf-8
#

from logzero import logger
from tornado.auth import OAuth2Mixin

from .auth import AuthError, OpenIdMixin, GithubOAuth2Mixin
from .base import BaseRequestHandler

from ..settings import AUTH_BACKENDS, GITHUB


class OpenIdLoginHandler(BaseRequestHandler, OpenIdMixin):
    _OPENID_ENDPOINT = AUTH_BACKENDS['openid']['endpoint']

    async def get(self):
        if self.get_argument("openid.mode", False):
            try:
                user = await self.get_authenticated_user()
            except AuthError as e:
                self.write(
                    "<code>Auth error: {}</code> <a href='/login'>Login</a>".
                    format(e))
            else:
                logger.info("User info: %s", user)
                await self.set_current_user(user['email'], user['name'])
                next_url = self.get_argument('next', '/')
                self.redirect(next_url)
        else:
            self.authenticate_redirect()


class SimpleLoginHandler(BaseRequestHandler):
    def get(self):
        self.set_cookie("next", self.get_argument("next", "/"))
        self.write('<html><body><form action="/login" method="post">'
                   '<div>首次登陆，请联系@蛮僧</div>'
                   '<div><input type="text" name="name" required placeholder="用户名(必填)"></div>'
                   '<div><input type="text" name="email" placeholder="邮箱"></div>'
                   '<div><input type="submit" value="Sign in"></div>'
                   '</form></body></html>')

    async def post(self):
        name = self.get_argument("name")
        email = self.get_argument('email', name+"@anonymous.com",strip=True)
        
        if email.strip() == '':
            email = name+"@anonymous.com"
            
        logger.info(name)     
        logger.info(email)        
        
        await self.set_current_user(email, name)
        next_url = self.get_cookie("next", "/")
        self.clear_cookie("next")
        self.redirect(next_url)


class GithubLoginHandler(BaseRequestHandler, GithubOAuth2Mixin):

    async def get(self):
        if self.get_argument('code', False):
            access = await self.get_authenticated_user(
                redirect_uri=GITHUB['redirect_uri'],
                client_id=GITHUB['client_id'],
                client_secret=GITHUB['client_secret'],
                code=self.get_argument('code'))
            http = self.get_auth_http_client()

            response = await http.fetch(
                "https://api.github.com/user",
                headers={"Authorization": "token " + access["access_token"]}
            )
            user = escape.json_decode(response.body)
            logger.info("User info: %s", user)
            await self.set_current_user(user['email'], user['name'])
            next_url = self.get_argument('next', '/')
            self.redirect(next_url)
        # Save the user and access token with
        # e.g. set_secure_cookie.
        else:
            await self.authorize_redirect(
                redirect_uri=GITHUB['redirect_uri'],
                client_id=GITHUB['client_id'],
                scope=['user'],
                response_type='code',
                extra_params={'approval_prompt': 'auto'})


class TuyaSSOLoginHandler(BaseRequestHandler):
    async def get(self):
        self.set_cookie("next", self.get_argument("next", "/"))
        self.write('<html><body><form action="/login" method="post">'
                   '<h3>首次登陆</h3>'
                   '<div"><input type="text" name="sso" required placeholder="请输入SSO"><input type="submit" value="提交"></div>'
                   '</form>'
                   '<h4>旧版登陆</h4>'
                   '<form action="/login" method="post">'
                   '<div></div>'
                   '<div"><input type="text" name="name" required placeholder="用户名（必填）">'
                   '<div"><input type="text" name="email" placeholder="邮箱">'
                   '<input type="submit" value="提交"></div>'
                   '</form>'
                   '</body></html>')
    
    async def post(self):
        sso = self.get_argument("sso",None)
        if sso:
            logger.info(sso)
        
            import requests
            response = requests.get(
                "https://login-cn.tuya-inc.com:7799/getLoginUser.sso",
                headers={"Cookie": "SSO_USER_TOKEN=" + sso}
            )
            response.raise_for_status()

            ret_json = response.json()
            logger.info(ret_json)

            if ret_json['result']['isLogin']:
                user = ret_json['result']['user']
                email = user['email']
                name = user['nick']
            else:
                self.write(response.text)
                return 
        
        else:
            name = self.get_argument("name")
            email = self.get_argument('email',None)
        
            if not email:
                email = name+"@tuya.com"
            
            users = await self.get_user_exist(email)
            if len(users)<=0:
                self.write('首次登陆，请使用sso注册')
                return 
            
        await self.set_current_user(email, name)
        next_url = self.get_cookie("next", "/")
        self.clear_cookie("next")
        self.redirect(next_url)
       