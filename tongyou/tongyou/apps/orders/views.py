from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal
import json
from django import http
from django.utils import timezone
from django.db import transaction


from users.models import Address
from goods.models import SKU
from .models import OrderInfo, OrderGoods
from tongyou.utils.response_code import RETCODE

class OrderSettlementView(LoginRequiredMixin, View):
    """结算订单"""
    def get(self, request):
        """提供订单结算页面"""
        # 获取登录用户
        user = request.user

        addresses = Address.objects.filter(user=user, is_deleted=False)

        redis_conn = get_redis_connection('carts')
        # 获取redis.hash中的购物车数据
        redis_cart = redis_conn.hgetall('carts_%s' % user.id)
        # 获取redis.map中的选中状态
        cart_selected = redis_conn.smembers('selected_%s' % user.id)
        # 将redis中的数据包装成大字典
        cart_dict = {}
        for sku_id in cart_selected:
            cart_dict[int(sku_id)] = int(redis_cart[sku_id])

        sku_qs = SKU.objects.filter(id__in=cart_dict.keys())
        total_count = 0  # 总数量
        total_amount = Decimal(0.00)  # 总金额
        payment_amount = Decimal(0.00)  # 实付金额

        for sku in sku_qs:
            sku.count = cart_dict[sku.id]
            sku.amount = sku.price * sku.count
            total_count += sku.count
            total_amount += sku.amount

        # 补充运费
        freight = Decimal('10.00')
        payment_amount = total_amount + freight
        context = {
            'addresses': addresses,
            'skus': sku_qs,
            'total_count': total_count,
            'total_amount': total_amount,
            'freight': freight,
            'payment_amount': payment_amount

        }
        return render(request, 'place_order.html', context)


class OrderCommitView(LoginRequiredMixin, View):
    """订单提交"""

    def post(self, request):
        """保存订单信息和订单商品信息"""
        # 获取数据
        json_dict = json.loads(request.body)
        address_id = json_dict.get('address_id')
        pay_method = json_dict.get('pay_method')

        # 校验参数
        if not all([address_id, pay_method]):
            return http.HttpResponseForbidden('缺少必传参数')

        try:
            address = Address.objects.get(id=address_id, is_deleted=False)

        except Exception as e:
            return http.HttpResponseForbidden('参数address_id错误')

        try:
            pay_method = int(pay_method)
        except Exception as e:
            return http.HttpResponseForbidden('参数pay_method错误')
        if pay_method not in [OrderInfo.PAY_METHODS_ENUM['CASH'], OrderInfo.PAY_METHODS_ENUM['ALIPAY']]:
            return http.HttpResponseForbidden('参数pay_method错误')

        # 获取登录用户
        user = request.user

        # 生成订单信息
        order_id = timezone.now().strftime('%Y%m%d%H%M%S') + ('%09d' % user.id)
        if pay_method == OrderInfo.PAY_METHODS_ENUM['CASH']:
            status = OrderInfo.ORDER_STATUS_ENUM['UNSEND']
        else:
            status = OrderInfo.ORDER_STATUS_ENUM['UNPAID']

        # 定义一个事务
        with transaction.atomic():
            # 创建事务保存点
            save_id = transaction.savepoint()

            try:
                order = OrderInfo.objects.create(
                    order_id=order_id,
                    user=user,
                    address=address,
                    total_count=0,
                    total_amount=Decimal('0.00'),
                    freight=Decimal('10.00'),
                    pay_method=pay_method,
                    status=status
                )

                # 连接数据库
                redis_conn = get_redis_connection('carts')

                # 获取redis.hash中的购物车数据
                redis_cart = redis_conn.hgetall('carts_%s' % user.id)
                # 获取redis.map中的选中状态
                cart_selected = redis_conn.smembers('selected_%s' % user.id)

                # 将redis中的数据包装成大字典
                cart_dict = {}
                for sku_id in cart_selected:
                    cart_dict[int(sku_id)] = int(redis_cart[sku_id])


                for sku_id in cart_dict:
                    while True:
                        # 判断库存是否充足
                        sku = SKU.objects.get(id=sku_id)
                        count = cart_dict[sku_id]
                        origin_stock = sku.stock
                        origin_sales = sku.sales
                        if count > origin_stock:
                            # 如果库存不足,回滚并响应
                            transaction.savepoint_rollback(save_id)
                            return http.JsonResponse({'code': RETCODE.STOCKERR, 'errmsg': '库存不足'})

                        # 修改sku库存和销量
                        new_stock = origin_stock - count
                        new_sales = origin_sales + count

                        # 乐观锁:如果相同，表示没人修改，可以更新库存，否则表示别人抢过资源，不再执行库存更新
                        result = SKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                        if result == 0:
                            continue  # 循环提交订单

                        # 修改SPU销量
                        sku.spu.sales += count
                        sku.spu.save()

                        # 保存订单商品信息
                        OrderGoods.objects.create(
                            order=order,
                            sku=sku,
                            count=count,
                            price=sku.price,

                        )

                        # 保存商品订单中总价和总数量
                        order.total_count += count
                        order.total_amount += (sku.price * count)
                        # 下单成功或者失败就跳出循环
                        break

                    # 添加邮费和保存订单信息
                    order.total_amount += order.freight
                    order.save()

            except Exception as e:
                transaction.savepoint_rollback(save_id)
                return http.JsonResponse({'code': RETCODE.DBERR, 'errmsg': '下单失败'})
            else:
                # 提交订单成功，显式的提交一次事务
                transaction.savepoint_commit(save_id)



        # 清除购物车中已结算的商品
        pl = redis_conn.pipeline()
        pl.hdel('carts_%s' % user.id, *cart_selected)
        pl.srem('selected_%s' % user.id, *cart_selected)
        pl.execute()

        # 响应提交订单结果
        return http.JsonResponse({'code': RETCODE.OK, 'errmsg': '下单成功', 'order_id': order.order_id})

class OrderSuccessView(LoginRequiredMixin, View):
    """提交订单成功"""

    def get(self, request):
        order_id = request.GET.get('order_id')
        payment_amount = request.GET.get('payment_amount')
        pay_method = request.GET.get('pay_method')
        # 校验
        try:
            OrderInfo.objects.get(order_id=order_id, pay_method=pay_method, total_amount=payment_amount)
        except Exception as e:
            return http.HttpResponseForbidden('订单有误')

        context = {
            'order_id': order_id,
            'payment_amount': payment_amount,
            'pay_method': pay_method
        }
        return render(request, 'order_success.html', context)

class OrderInfoView(LoginRequiredMixin, View):
    """订单信息展示"""

    def get(self, request, page_num):

        user = request.user
        order_pages = OrderInfo.objects.filter(user=user).order_by('-create_time', '-order_id')
        for order in order_pages:
            skus = OrderGoods.objects.filter(order_id=order.order_id)
            for sku in skus:
                sku.amount = sku.price * sku.count

            order.sku_list = skus
            order.status_name = OrderInfo.ORDER_STATUS_CHOICES[order.status]
            order.pay_method_name = OrderInfo.PAY_METHOD_CHOICES[order.pay_method - 1]

        # 分页
        page_num = int(page_num)
        page = 5  # 每页展示5个
        page_count = order_pages.count() // page + (order_pages.count() % 5 and 1)
        order_pages = order_pages[(page_num - 1) * page: page_num * page]
        context = {
            'order_pages': order_pages,
            'total_page': page_count,
            'page_num': page_num
        }
        return render(request, 'user_center_order.html', context)