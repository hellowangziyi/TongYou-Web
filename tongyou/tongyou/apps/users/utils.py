from django.contrib.auth.backends import ModelBackend
import re
from .models import User

def get_user_by_account(account):
    """
    根据account查询用户
    :param account: 用户名或者手机号
    :return: user
    """
    try:
        if re.match(r'^1[3-9]\d{9}$', account):
            user = User.objects.get(mobile=account)
        else:
            user = User.objects.get(username=account)

        return user
    except User.DoesNotExist:
        return None



class UsernameMobileAuthBackend(ModelBackend):
    # 多账号登录验证
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 1.根据用户名或手机号 查询user
        user = get_user_by_account(username)
        # 2.校验用户密码
        if user and user.check_password(password):
        # 3.返回user or none
            return user
