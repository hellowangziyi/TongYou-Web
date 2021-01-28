from django.shortcuts import render
from django.views import View
from QQLoginTool.QQtool import OAuthQQ
from django import http

from tongyou.utils.response_code import RETCODE

# Create your views here.

QQ_CLIENT_ID = '101518219'
QQ_CLIENT_SECRET = '418d84ebdc7241efb79536886ae95224'
QQ_REDIRECT_URI = 'http://www.meiduo.site:8000/oauth_callback'


class QQAuthURLView(View):
    def get(self, request):
        """提供QQ登录页面网址
            https://graph.qq.com/oauth2.0/authorize?response_type=code&client_id=xxx&redirect_uri=xxx&state=xxx
        """
        # 获取查询参数
        next = request.GET.get('next') or '/'
        # 创建oauth对象
        oauth_qq = OAuthQQ(client_id=QQ_CLIENT_ID, client_secret=QQ_CLIENT_SECRET, redirect_uri=QQ_REDIRECT_URI, state=next)
        login_url = oauth_qq.get_qq_url()
        data = {
            'code': RETCODE.OK,
            'errmsg': 'OK',
            'login_url': login_url
        }
        return http.JsonResponse(data)


class QQAuthUserView(View):
    """用户扫码登录的回调处理"""
    pass