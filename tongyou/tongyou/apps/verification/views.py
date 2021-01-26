from django.shortcuts import render

# Create your views here.
from django.views import View
from tongyou.utils.captcha.captcha import captcha
from django_redis import get_redis_connection
from django import http

class ImageCodeView(View):
    def get(self, request, uuid):
        # 调用SDK生产图像验证码
        name, text, image_bytes = captcha.generate_captcha()
        # 创建redis连接
        redis_con = get_redis_connection('verify_code')

        # 将图像验证码字符串内容存储到redis
        redis_con.setex(uuid, 300, text)
        # request.session['uuid'] = uuid
        # 将图形bytes数据响应给前端
        return http.HttpResponse(image_bytes, content_type='image/png')


