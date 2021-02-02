from django.shortcuts import render

# Create your views here.
from django.views import View
from django.shortcuts import render
from goods.models import GoodsChannel, GoodsCategory
from .utils import get_categories

class IndexView(View):
    def get(self, request):
        """提供首页广告界面"""
        # 查询商品频道和分类
        categories = get_categories()
        # 渲染模板的上下文
        context = {
            'categories': categories,
        }
        return render(request, 'index.html', context)