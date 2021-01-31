from django.contrib.auth.backends import ModelBackend
import re
from .models import User
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer, BadData
from django.conf import settings

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


def generate_verify_email_url(user):
    """
        生成邮箱验证链接
        :param user: 当前登录用户
        :return: verify_url
    """
    # 创建加密实例对象
    serializer = Serializer(secret_key=settings.SECRET_KEY, expires_in=3600 * 24)

    # 包装要加密的字典数据
    data = {
        'user_id':user.id,
        'email':user.email
    }
    # 加密
    token = serializer.dumps(data).decode()
    verify_url = settings.EMAIL_VERIFY_URL + '?token=' + token
    return verify_url



def check_verify_email_token(token):
    """
    验证token并提取user
    :param token: 用户信息签名后的结果
    :return: user, None
    """
    # 创建加密实例对象
    serializer = Serializer(settings.SECRET_KEY, expires_in=3600 * 24)
    try:
        # loads
        data = serializer.loads(token)

        user_id = data.get('user_id')
        email = data.get('email')
        try:
            user = User.objects.get(id=user_id, email=email)
        except User.DoesNotExist:
            return None
        else:
            return user
    except BadData:
        return None
