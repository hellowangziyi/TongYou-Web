from django.shortcuts import render
from django.views import View
from django.shortcuts import render
from django import http

from .models import GoodsChannel, GoodsCategory, SKU
from contents.utils import get_categories
from .utlis import get_breadcrumb
from tongyou.utils.response_code import RETCODE


# Create your views here.
class ListView(View):
    """商品列表页"""
    def get(self, request, category_id, page_num):

        # 校验数据
        try:
            cat3 = GoodsCategory.objects.get(id=category_id)
        except Exception as e:
            return http.HttpResponseForbidden('GoodsCategory 不存在')

        # 获取排序参数
        sort = request.GET.get('sort', 'default')
        if sort == 'price':
            sort_field = '-price'
        elif sort == 'hot':
            sort_field = '-sales'
        else:
            sort = 'default',
            sort_field = '-create_time'

        # 查询所有要展示的商品
        sku_qs = cat3.sku_set.filter(is_launched=True).order_by(sort_field)

        # 分页
        page_num = int(page_num)
        page = 5   # 每页展示5个
        page_count = sku_qs.count() // page + (sku_qs.count() % 5 and 1)
        page_skus = sku_qs[(page_num - 1) * page: page_num * page]



        context = {
            # 商品分类数据
            'categories': get_categories(),
            # 面包屑导航数据
            'breadcrumb': get_breadcrumb(cat3),
            # 三级类别
            'category': cat3,
            # 页数
            'page_num': page_num,
            # 总页数
            'total_page': page_count,
            # sku商品数据
            'page_skus': page_skus,
            # 排序
            'sort': sort
        }


        return render(request, 'list.html', context)


class HotGoodsView(View):
    """商品热销排行"""
    def get(self, request, category_id):
        # 校验数据
        try:
            cat3 = GoodsCategory.objects.get(id=category_id)
        except Exception as e:
            return http.HttpResponse('GoodsCategory 不存在')

        # 查询当前三级类别下所有商品，按销量排序
        sku_qs = cat3.sku_set.filter(is_launched=True).order_by('-sales')[0:2]

        # 模型转字典
        hot_skus = []
        for sku in sku_qs:
            hot_skus.append({
                'id': sku.id,
                'name': sku.name,
                'price': sku.price,
                'default_image_url': sku.default_image.url
            })


        return http.JsonResponse({'code':RETCODE.OK,'errmsg':'OK', 'hot_skus':hot_skus})