from django.shortcuts import render

# Create your views here
from django.views import View
from django import http
from django.shortcuts import render, redirect
import re
from django.contrib.auth import login, authenticate, logout
from django_redis import get_redis_connection
import json

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

        response = redirect('/')
        response.set_cookie('username', user.username, max_age=3600 * 24 * 14)
        return response

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


class ImageCodeTestView(View):
    # 校验图形验证码是否正确
    def get(self, request, uuid):
        image_code_client = request.GET.get('image_code')
        # 创建连接到redis的对象
        redis_conn = get_redis_connection('verify_code')
        # 提取图形验证码
        image_code_server = redis_conn.get(uuid)
        if image_code_server is None:
            # 图形验证码过期或者不存在
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图形验证码失效'})

        # 删除图形验证码，避免恶意测试图形验证码
        redis_conn.delete(uuid)

        # 对比图形验证码
        image_code_server = image_code_server.decode()  # bytes转字符串
        if image_code_client.lower() != image_code_server.lower():  # 转小写后比较
            return http.JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '输入图形验证码有误'})
        data = {

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
        # 获取登录来源
        next = request.GET.get('next')
        # 重定向到首页
        response = redirect(next or '/')
        response.set_cookie('username', user.username, max_age=3600*24*14)
        return response

class LogoutView(View):
    def get(self, request):
        """退出登录"""
        # 清除登录状态
        logout(request)
        # 创建响应对象
        response = redirect('user:login')
        response.delete_cookie('username')
        # 重定向
        return response

class InfoView(View):
    def get(self, request):
        """用户中心"""
        user = request.user
        if user.is_authenticated:
            # 如果是登录用户则正常跳转
            return render(request, 'user_center_info.html')
        else:
            # 否则重定向登录页面
            # return redirect('user:login')
            return redirect('/login/?next=/info/')

class EmailView(View):
    """设置用于邮箱并激活"""

    def put(self, request):
        # 1.接收请求体非表单数据  body
        json_dic = json.loads(request.body)
        email = json_dic.get('email')

        # 2.校验
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return http.HttpResponseForbidden('邮箱格式错误')

        # 3.修改user模型的email字段
        user = request.user

        User.objects.filter(username=user.username, email='').update(email=email)

        data = {
            'code': RETCODE.OK,
            'errmsg': '添加邮箱成功'
        }
        return http.JsonResponse(data)

class AddressView(View):
    def get(self, request):
        return render(request, 'user_center_site.html')