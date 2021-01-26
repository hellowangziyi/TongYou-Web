from django.shortcuts import render

# Create your views here
from django.views import View
from django import http
from django.shortcuts import render, redirect
import re
from django.contrib.auth import login, authenticate
from django_redis import get_redis_connection

from .models import User
from tongyou.utils.response_code import RETCODE


class RegisterView(View):
    # 注册
   def get(self, request):
        return render(request, 'register.html')

   def post(self, request):
       # 1.接受请求体表单数据 POST
        query_dic = request.POST
        username = query_dic.get('username')
        password = query_dic.get('password')
        password2 = query_dic.get('password2')
        mobile = query_dic.get('mobile')
        image_code = query_dic.get('image_code')
        allow = query_dic.get('allow')
       # 2.校验数据
        if not all([username, password, password2, mobile, image_code, allow]):
            return http.HttpResponseForbidden('缺少必传参数')

        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return http.HttpResponseForbidden('请输入5-20个字符的用户名')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return http.HttpResponseForbidden('请输入8-20位的密码')

        if password != password2:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('请输入正确的手机号码')

        if allow != 'on':
            return http.HttpResponseForbidden('请勾选用户协议')



       # 3. 创建User并存储到表中
        user = User.objects.create_user(username, password=password, mobile=mobile)

        # 状态保持
        # request.session['id'] = user.id
        login(request, user)

       # 4.响应
        return redirect('/')

class UsernameCountView(View):
    # 校验用户名是否重复
    def get(self, request, username):
        count = User.objects.filter(username=username).count()
        data = {
            'count': count,
            'code': RETCODE.OK,
            'errmsg': 'OK'
        }
        return http.JsonResponse(data)

class MobileCountView(View):
    # 校验手机号是否重复
    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()
        data = {
            'count': count,
            'code': RETCODE.OK,
            'errmsg': 'OK'

        }
        return http.JsonResponse(data)

class LoginView(View):
    def get(self, request):
        return render(request, 'login.html')
    def post(self, request):
        # 接受请求数据
        query_dic = request.POST
        username = query_dic.get('username')
        password = query_dic.get('password')
        remembered = query_dic.get('remembered')
        # 校验
        if all([username, password]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        # 用户登录验证
        user = authenticate(request, username=username, password=password)
        if user is None:
            return render(request, 'login.html', {'account_errmsg': '用户名或密码错误'})
        # 状态保持
        login(request, user)
        if remembered != 'on':
            request.session.set_expiry(0)

        # 重定向到首页
        return redirect('/')
