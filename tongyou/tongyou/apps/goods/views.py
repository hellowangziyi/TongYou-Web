from django.shortcuts import render
from django.views import View
from django.shortcuts import render
from django import http

from .models import GoodsChannel, GoodsCategory, SKU, SPU
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

class DetailView(View):
    """商品详情页"""

    def get(self, request, sku_id):
        # 获取当前sku的信息
        try:
            sku = SKU.objects.get(id=sku_id)
        except Exception as e:
            return http.HttpResponseForbidden("sku_id 不存在")

        # 获取当前sku所对应的三级分类
        category = sku.category

        # 查询当前sku所对应的spu
        spu = sku.spu

        """1.准备当前商品的规格选项列表 [8, 11]"""
        # 获取出当前正显示的sku商品的规格选项id列表
        sku_spec_qs = sku.specs.order_by('spec_id')
        sku_option_ids = []
        for sku_spec in sku_spec_qs:
            sku_option_ids.append(sku_spec.option_id)

        """2.构造规格选择仓库
                {(8, 11): 3, (8, 12): 4, (9, 11): 5, (9, 12): 6, (10, 11): 7, (10, 12): 8}
        """
        # 构造规格选择仓库
        temp_sku_qs = spu.sku_set.all()   # 获取当前spu下的所有sku
        spec_sku_map = {}
        for temp_sku in temp_sku_qs:
            # 查询每一个sku的规格数据
            temp_spec_qs = temp_sku.specs.order_by('spec_id')
            temp_sku_option_ids = []   # 用来包装每个sku的选项值
            for temp_spec in temp_spec_qs:
                temp_sku_option_ids.append(temp_spec.option_id)
            spec_sku_map[tuple(temp_sku_option_ids)] = temp_sku.id

        """3.组合 并找到sku_id 绑定"""
        spu_spec_qs =spu.specs.order_by('id')  # 获取当前spu中的所有规格
        for index, spec in enumerate(spu_spec_qs):
            spec_option_qs = spec.options.all()
            temp_option_ids = sku_option_ids[:]
            for option in spec_option_qs:
                temp_option_ids[index] = option.id
                option.sku_id = spec_sku_map.get(tuple(temp_option_ids))
            spec.spec_options = spec_option_qs


        # 查询商品频道分类
        categories = get_categories()
        # 查询面包屑导航
        breadcrumb = get_breadcrumb(category)

        # 渲染页面
        context = {
            'categories': categories,
            'breadcrumb': breadcrumb,
            'sku': sku,
            'spu': spu,
            'spec_qs': spu_spec_qs,
            'category': category

        }
        return render(request, 'detail.html', context)