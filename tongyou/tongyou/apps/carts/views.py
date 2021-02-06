from django.shortcuts import render
from django.views import View
import json, base64, pickle
from django import http
from django_redis import get_redis_connection
from django.shortcuts import render

from goods.models import SKU
from tongyou.utils.response_code import RETCODE
# Create your views here.

class CartsView(View):
    """购物车"""
    def post(self, request):
        """添加购物车"""
        # 接收参数
        json_dict = json.loads(request.body)
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)

        # 校验参数
        if all([sku_id, count]) is False:
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            sku = SKU.objects.get(id=sku_id, is_launched=True)
        except Exception as e:
            return http.HttpResponseForbidden('sku_id不存在')

        try:
            count = int(count)
        except Exception as e:
            return http.HttpResponseForbidden('参数count有误')

        if isinstance(selected, bool) is False:
            return http.HttpResponseForbidden('参数selected有误')

        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录用户，操作redis购物车
            """
            hash:{sku_id:count}
            map:{sku_id}
            """
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()
            # 新增购物车数据
            pl.hincrby('carts_%s' % user.id, sku_id, count)
            # 新增选中的状态
            if selected:
                pl.sadd('selected_%s' % user.id, sku_id)
            # 执行管道
            pl.execute()
            # 响应结果
            return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功'})

        else:
            # 未登录用户，操作cookie购物车

            cart_str = request.COOKIES.get('carts')
            if cart_str:
                # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                bytes_str = cart_str.encode()
                bytes_un = base64.b64decode(bytes_str)
                cart_dict = pickle.loads(bytes_un)

                if sku_id in cart_dict:
                    origin_count = cart_dict[sku_id]['count']
                    count += origin_count
            else:  # 用户从没有操作过cookie购物车
                cart_dict = {}
            # 更新购物车
            cart_dict[sku_id] = {'count': count, 'selected': selected}

            # 将字典重新转字符串
            bytes_un = pickle.dumps(cart_dict)
            bytes_str = base64.b64encode(bytes_un)
            cart_str = bytes_str.decode()

            # 创建响应对象
            response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功'})
            # 响应结果并将购物车数据写入到cookie
            response.set_cookie('carts', cart_str)
            return response

    def get(self, request):
        """展示购物车"""
        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录用户，操作redis购物车
            redis_conn = get_redis_connection('carts')

            # 获取redis.hash中的购物车数据
            redis_cart = redis_conn.hgetall('carts_%s' % user.id)
            # 获取redis.map中的选中状态
            cart_selected = redis_conn.smembers('selected_%s' % user.id)

            # 将redis中的数据包装成大字典
            cart_dict = {}
            for sku_id in redis_cart:
                cart_dict[int(sku_id)] = {
                    'count': int(redis_cart[sku_id]),
                    'selected': sku_id in cart_selected
                }

        else:  # 未登录用户，查询cookie购物车
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                bytes_str = cart_str.encode()
                bytes_un = base64.b64decode(bytes_str)
                cart_dict = pickle.loads(bytes_un)
            else:
                return render(request, 'cart.html')

        # 查询sku模型
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        sku_list = []
        for sku_model in sku_qs:
            count = cart_dict[sku_model.id]['count']
            sku_list.append({
                'id': sku_model.id,
                'name': sku_model.name,
                'default_image_url': sku_model.default_image.url,
                'price': str(sku_model.price),
                'count': count,
                'amount': str(sku_model.price * count),
                'selected': str(cart_dict[sku_model.id]['selected'])

            })

        return render(request, 'cart.html', {'cart_skus': sku_list})

    def put(self, request):
        """修改购物车"""
        # 接收参数
        json_dict = json.loads(request.body)
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected')

        # 校验参数
        if not all([sku_id, count]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            return http.HttpResponseForbidden('商品sku_id不存在')

        try:
            count = int(count)
        except Exception as e:
            return http.HttpResponseForbidden('参数count有误')

        if isinstance(selected, bool) is False:
            return http.HttpResponseForbidden('参数selected有误')

        cart_sku = {
            'id': sku_id,
            'name': sku.name,
            'count': count,
            'selected': selected,
            'price': sku.price,
            'amount': sku.price * count,
            'default_image_url': sku.default_image.url
        }
        # 创建响应对象
        response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_sku': cart_sku})

        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录用户，操作redis购物车
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()

            pl.hset('carts_%s' % user.id, sku_id, count)
            if selected:
                pl.sadd('selected_%s' % user.id, sku_id)
            else:
                pl.srem('selected_%s' % user.id, sku_id)

            pl.execute()

        else:  # 未登录用户，修改cookie购物车
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                bytes_str = cart_str.encode()
                bytes_un = base64.b64decode(bytes_str)
                cart_dict = pickle.loads(bytes_un)

                if sku_id in cart_dict:
                    origin_count = cart_dict[sku_id]['count']
                    count += origin_count
            else:
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': 'cookie数据没有获取到'})

            cart_dict[sku_id] = {'count': count, 'selected': selected}
            # 将字典重新转字符串
            bytes_un = pickle.dumps(cart_dict)
            bytes_str = base64.b64encode(bytes_un)
            cart_str = bytes_str.decode()

            # 响应结果并将购物车数据写入到cookie
            response.set_cookie('carts', cart_str)

        return response

    def delete(self, request):
        """删除购物车"""
        # 接收和校验参数
        json_dict = json.loads(request.body)
        sku_id = json_dict.get('sku_id')

        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            return http.HttpResponseForbidden('sku_id不存在')

        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录用户，删除redis购物车
            redis_conn = get_redis_connection('carts')
            pl = redis_conn.pipeline()
            pl.hdel('carts_%s' % user.id, sku_id)
            pl.srem('selected_%s' % user.id, sku_id)
            pl.execute()
            return http.JsonResponse({'code': RETCODE.OK, 'errmsg': "删除购物车成功"})
        else:
            # 未登录用户，删除cookie购物车
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                bytes_str = cart_str.encode()
                bytes_un = base64.b64decode(bytes_str)
                cart_dict = pickle.loads(bytes_un)
            else:
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': 'cookie数据没获取到'})

            if sku_id in cart_dict:
                del cart_dict[sku_id]

            # 判断当前字典是为空,如果为空 将cookie删除
            response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': "删除购物车成功"})
            if not cart_dict:
                response.delete_cookie('carts')
            else:
                # 将字典重新转字符串
                bytes_un = pickle.dumps(cart_dict)
                bytes_str = base64.b64encode(bytes_un)
                cart_str = bytes_str.decode()
                response.set_cookie('carts', cart_str)

            return response

class CartsSelectAllView(View):
    """全选购物车"""

    def put(self, request):
        # 接收参数
        json_dict = json.loads(request.body.decode())
        selected = json_dict.get('selected', True)

        # 校验参数
        if selected:
            if not isinstance(selected, bool):
                return http.HttpResponseForbidden('参数selected有误')

        # 判断用户是否登录
        user = request.user
        if user.is_authenticated:
            # 登录用户，操作redis购物车
            redis_conn = get_redis_connection('carts')
            sku_ids = redis_conn.hgetall('carts_%s' % user.id)
            sku_id_list = sku_ids.keys()
            if selected:
                # 全选
                for sku_id in sku_id_list:
                    redis_conn.sadd('selected_%s' % user.id, sku_id)
            else:
                # 取消全选
                redis_conn.delete('selected_%s' % user.id)
            return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})

        else:
            # 未登录用户，操作cookie购物车
            cart_str = request.COOKIES.get('carts')
            if not cart_str:
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': 'cookie没有获取到'})

            # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
            bytes_str = cart_str.encode()
            bytes_un = base64.b64decode(bytes_str)
            cart_dict = pickle.loads(bytes_un)

            # 遍历cookie购物车大字典,将内部的每一个selected修改为True 或 False

            for sku_id in cart_dict:
                cart_dict[sku_id]['selected'] = selected

            # 将字典重新转字符串
            bytes_un = pickle.dumps(cart_dict)
            bytes_str = base64.b64encode(bytes_un)
            cart_str = bytes_str.decode()

            response = http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK'})
            response.set_cookie('carts', cart_str)
            return response


class CartsSimpleView(View):
    """商品页面右上角购物车"""
    def get(self, request):
        """展示商品页面简单购物车"""
        user = request.user
        # 判断用户是否登录
        if user.is_authenticated:
            # 登录用户，操作redis购物车
            redis_conn = get_redis_connection('carts')

            # 获取redis.hash中的购物车数据
            redis_cart = redis_conn.hgetall('carts_%s' % user.id)

            # 将redis中的数据包装成大字典
            cart_dict = {}
            for sku_id in redis_cart:
                cart_dict[int(sku_id)] = {
                    'count': int(redis_cart[sku_id]),

                }

        else:  # 未登录用户，查询cookie购物车
            cart_str = request.COOKIES.get('carts')
            if cart_str:
                bytes_str = cart_str.encode()
                bytes_un = base64.b64decode(bytes_str)
                cart_dict = pickle.loads(bytes_un)
            else:
                cart_dict = {}

        # 查询sku模型
        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        sku_list = []
        for sku_model in sku_qs:
            sku_list.append({
                'id': sku_model.id,
                'name': sku_model.name,
                'default_image_url': sku_model.default_image.url,
                'count': cart_dict[sku_model.id]['count']
            })

        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'cart_skus': sku_list})