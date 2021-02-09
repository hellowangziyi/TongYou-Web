import base64, pickle
from django_redis import get_redis_connection


def merge_cart_cookie_to_redis(request, response):
    """
       登录时合并购物车
       :param request: 登录时借用过来的请求对象
       :param user: 登录时借用过来的用户对象
       :param response: 借用过来准备做删除cookie的响应对象
       :return:
    """
    # 获取cookie购物车数据
    cart_str = request.COOKIES.get('carts')

    if not cart_str:
        # 无cookie数据
        return

    # 字典转字符串
    bytes_str = cart_str.encode()
    bytes_un = base64.b64decode(bytes_str)
    cart_dict = pickle.loads(bytes_un)

    redis_conn = get_redis_connection('carts')
    user = request.user
    pl = redis_conn.pipeline()

    for sku_id in cart_dict:
        # 修改count
        pl.hset('carts_%s' % user.id, sku_id, cart_dict[sku_id]['count'])
        # 修改selected
        if cart_dict[sku_id]['selected']:
            pl.sadd('selected_%s' % user.id, sku_id)
        else:
            pl.srem('selected_%s' % user.id)

    pl.execute()

    # 删除cookie购物车数据
    response.delete_cookie('carts')
