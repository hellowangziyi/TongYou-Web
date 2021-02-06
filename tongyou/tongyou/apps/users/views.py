from django.shortcuts import render

# Create your views here
from django.views import View
from django import http
from django.shortcuts import render, redirect
import re
from django.contrib.auth import login, authenticate, logout
from django_redis import get_redis_connection
import json
from django.db import DataError
import logging
from django.core.mail import send_mail
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import User, Address
from tongyou.utils.response_code import RETCODE
from celery_tasks.email.tasks import send_verify_email
from .utils import generate_verify_email_url, check_verify_email_token
from goods.models import SKU
from carts.utils import merge_cart_cookie_to_redis


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
        merge_cart_cookie_to_redis(request, response)
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

class EmailView(LoginRequiredMixin, View):
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

        # 发送邮件
        # html_message = '<p>尊敬的用户您好！</p>'
        # send_mail(subject='tongyou邮箱验证', message='正文', from_email='童游武汉<hellowzzzy@163.com>', recipient_list=[email], html_message=html_message)


        # 异步发送验证邮件
        verify_url = generate_verify_email_url(user)
        send_verify_email.delay(email, verify_url)

        data = {
            'code': RETCODE.OK,
            'errmsg': '添加邮箱成功'
        }
        return http.JsonResponse(data)


class VerifyEmailView(LoginRequiredMixin, View):
    """验证邮箱"""
    def get(self, request):
        # 接受查询参数中的token
        token = request.GET.get('token')
        # token解密，根据用户信息查询到指定user
        user = check_verify_email_token(token)
        if not user:
            return http.HttpResponseForbidden('无效的token')
        # 修改user的email_active
        try:
            user.email_active = True
            user.save()
        except Exception as e:
            return http.HttpResponseServerError('激活邮件失败')

        # 响应
        return redirect('user:info')

class AddressView(LoginRequiredMixin, View):
    def get(self, request):
        """提供收货地址界面"""
        # 获取用户地址列表
        user = request.user
        addresses = Address.objects.filter(user=user, is_deleted=False)

        address_list = []
        for address in addresses:
            address_list.append({
                'id': address.id,
                'title': address.title,
                'receiver': address.receiver,
                'province_id': address.province.id,
                'province': address.province.name,
                'city_id': address.city.id,
                'city': address.city.name,
                'district_id': address.district.id,
                'district': address.district.name,
                'place': address.place,
                'mobile': address.mobile,
                'tel': address.tel,
                'email': address.email
            })
        context = {
            'addresses': address_list,
            'default_address_id': 1,
        }
        return render(request, 'user_center_site.html', context)


class AddressCreateView(LoginRequiredMixin, View):
    """创建收货地址"""
    def post(self, request):
        # 1.获取查询参数
        json_dic = json.loads(request.body)
        title = json_dic.get('title')
        receiver = json_dic.get('receiver')
        province_id = json_dic.get('province_id')
        city_id = json_dic.get('city_id')
        district_id = json_dic.get('district_id')
        place = json_dic.get('place')
        mobile = json_dic.get('mobile')
        tel = json_dic.get('tel')
        email = json_dic.get('email')

        # 2.校验数据
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        # 3.保存地址信息
        try:
            address = Address.objects.create(
                user=request.user,
                title=receiver,
                receiver=receiver,
                province_id=province_id,
                city_id=city_id,
                district_id=district_id,
                place=place,
                mobile=mobile,
                tel=tel,
                email=email
            )
        except DataError as e:

            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '新增地址失败'})

        # 设置默认地址
        if request.user.default_address is None:
            request.user.default_address = address

        address_dict = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province_id': address.province.id,
            'province': address.province.name,
            'city_id': address.city.id,
            'city': address.city.name,
            'district_id': address.district.id,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email
        }

        # 响应保存结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '新增地址成功', 'address': address_dict})


class UpdateDestroyAddressView(LoginRequiredMixin, View):
    def put(self, request, address_id):
        """修改收货地址"""
        user = request.user


        # 获取查询参数
        json_dic = json.loads(request.body)
        title = json_dic.get('title')
        receiver = json_dic.get('receiver')
        province_id = json_dic.get('province_id')
        city_id = json_dic.get('city_id')
        district_id = json_dic.get('district_id')
        place = json_dic.get('place')
        mobile = json_dic.get('mobile')
        tel = json_dic.get('tel')
        email = json_dic.get('email')

        # 校验数据
        if not all([receiver, province_id, city_id, district_id, place, mobile]):
            return http.HttpResponseForbidden('缺少必传参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return http.HttpResponseForbidden('参数mobile有误')
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return http.HttpResponseForbidden('参数tel有误')
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return http.HttpResponseForbidden('参数email有误')

        # 更新地址信息
        address = Address.objects.get(id=address_id)

        address.title = title
        address.receiver = receiver
        address.province_id = province_id
        address.city_id = city_id
        address.district_id = district_id
        address.place = place
        address.mobile = mobile
        address.tel = tel
        address.email = email
        address.save()

        address_dict = {
            'id': address.id,
            'title': address.title,
            'receiver': address.receiver,
            'province_id': address.province.id,
            'province': address.province.name,
            'city_id': address.city.id,
            'city': address.city.name,
            'district_id': address.district.id,
            'district': address.district.name,
            'place': address.place,
            'mobile': address.mobile,
            'tel': address.tel,
            'email': address.email
        }

        # 响应保存结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '新增地址成功', 'address': address_dict})
    def delete(self, request, address_id):
        """删除地址"""
        try:
            address = Address.objects.get(id=address_id)

            address.is_deleted=True
            address.save()

        except Exception as e:
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '删除地址失败'})

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})


class UpdateTitleAddressView(LoginRequiredMixin, View):
    """设置地址标题"""
    def put(self, request, address_id):

        # 接收参数：地址标题
        user = request.user
        json_dic = json.loads(request.body)
        title = json_dic.get('title'

                             )
        try:
            # 查询地址
            address = Address.objects.get(id=address_id, user=user, is_deleted=False)

            # 设置新的地址标题
            address.title = title
            address.save()
        except Exception as e:
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '设置地址标题失败'})

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '设置地址标题成功'})


class DefaultAddressView(LoginRequiredMixin, View):
    """设置默认地址"""
    def put(self, request, address_id):
        """设置默认地址"""
        # 接收参数：地址标题
        user = request.user

        try:
            # 查询地址
            address = Address.objects.get(id=address_id, user=user, is_deleted=False)

            # 设置新的地址标题
            user.default_address = address
            user.save()
        except Exception as e:
            return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '设置默认地址失败'})

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '设置默认地址成功'})

class ChangePasswordView(LoginRequiredMixin, View):
    """修改密码"""
    def get(self, request):
        """""展示修改密码界面"""
        return render(request, 'user_center_pass.html')

    def post(self, request):
        """""修改密码"""
        # 接收参数
        query_dict = request.POST
        new_pwd = query_dict.get('new_pwd')
        old_pwd = query_dict.get('old_pwd')
        new_cpwd = query_dict.get('new_cpwd')

        # 校验参数
        if not all([new_pwd, old_pwd, new_cpwd]):
            return http.HttpResponseForbidden('缺少必传参数')

        if request.user.check_password(old_pwd) is False:
            return render(request, 'user_center_pass.html', {'origin_pwd_errmsg': '原始密码错误'})

        if not re.match(r'^[0-9A-Za-z]{8,20}$', new_pwd):
            return http.HttpResponseForbidden('密码最少8位，最长20位')

        if new_pwd != new_cpwd:
            return http.HttpResponseForbidden('两次输入的密码不一致')

        # 修改密码
        try:
            request.user.set_password(new_pwd)
            request.user.save()
        except Exception as e:
            return render(request, 'user_center_pass.html', {'change_pwd_errmsg': '修改密码失败'})

        # 清理状态保持信息
        logout(request)
        response = redirect('user:login')
        response.delete_cookie('username')

        return response


class UserBrowseHistory(View):
    """用户浏览记录"""
    def post(self, request):
        """保存用户浏览记录"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return http.JsonResponse({'code': RETCODE.SESSIONERR, 'errmsg': '用户未登录'})


        # 接收参数
        json_dict = json.loads(request.body)
        sku_id = json_dict.get('sku_id')

        # 校验参数
        try:
            sku = SKU.objects.get(id=sku_id, is_launched=True)
        except Exception as e:
            return http.HttpResponseForbidden('sku_id 不存在')

        # 保存用户浏览数据
        redis_conn = get_redis_connection('history')
        pl = redis_conn.pipeline()

        # redis中的用户key
        key = 'history_%s' % user.id

        # 去重
        pl.lrem(key, 0, sku_id)
        # 添加到列表开头
        pl.lpush(key, sku_id)
        # 截取列表前五个元素
        pl.ltrim(key, 0, 4)
        # 执行管道
        pl.execute()

        return http.JsonResponse({'code':RETCODE.OK, 'errmsg':'OK'})

    def get(self, request):
        """获取用户浏览记录"""
        # 获取Redis存储的sku_id列表信息
        redis_conn = get_redis_connection('history')
        user = request.user
        key = 'history_%s' % user.id
        sku_ids = redis_conn.lrange(key, 0, -1)

        # 根据sku_ids列表数据，查询出商品sku信息
        sku_list = []
        for sku_id in sku_ids:
            sku_model = SKU.objects.get(id=sku_id)
            sku_list.append({
                'id':sku_model.id,
                'name':sku_model.name,
                'default_image_url':sku_model.default_image.url,
                'price':sku_model.price
            })

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'skus': sku_list})