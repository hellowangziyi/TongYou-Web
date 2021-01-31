from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^register/$', views.RegisterView.as_view()),
    url(r'^usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UsernameCountView.as_view()),
    url(r'^mobiles/(?P<mobile>1[345789]\d{9})/count/$', views.MobileCountView.as_view()),
    url(r'^image_code/test/(?P<uuid>[\w-]+)/$', views.ImageCodeTestView.as_view()),
    url(r'^login/$', views.LoginView.as_view(), name='login'),
    url(r'^logout/$', views.LogoutView.as_view(), name='logout'),
    url(r'^info/$', views.InfoView.as_view(), name='info'),
    # 添加邮箱
    url(r'^emails/$', views.EmailView.as_view(), name='emails'),
    # 验证邮箱
    url(r'^emails/verification/$', views.VerifyEmailView.as_view(), name='emails'),
    # 收货地址
    url(r'^addresses/$', views.AddressView.as_view(), name='addresses'),
    # 新增收货地址
    url(r'^addresses/create/$', views.AddressCreateView.as_view()),
    # 修改收货地址
    url(r'^addresses/(?P<address_id>\d+)/$', views.UpdateDestroyAddressView.as_view()),
    # 设置地址标题
    url(r'^addresses/(?P<address_id>\d+)/title/$', views.UpdateTitleAddressView.as_view()),
    # 设置默认地址
    url(r'^addresses/(?P<address_id>\d+)/default/$', views.DefaultAddressView.as_view()),
    # 修改密码
    url(r'^password/$', views.ChangePasswordView.as_view()),


]