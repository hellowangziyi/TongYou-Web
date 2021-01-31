from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tongyou.settings.dev")


# 创建celery实例
celery_app = Celery()
# 加载celery配置
celery_app.config_from_object('celery_tasks.config')
# 自动注册celery任务
celery_app.autodiscover_tasks(['celery_tasks.email'])