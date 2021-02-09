from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^orders/settlement/$', views.OrderSettlementView.as_view()),
    url(r'^orders/commit/$', views.OrderCommitView.as_view()),
    url(r'^orders/success/$', views.OrderSuccessView.as_view()),
    url(r'^orders/info/(?P<page_num>\d+)/$', views.OrderInfoView.as_view()),
]