from django.shortcuts import render
from django.views import View
from django_redis import get_redis_connection
from django.contrib.auth.mixins import LoginRequiredMixin
from decimal import Decimal

from users.models import Address
from goods.models import SKU

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