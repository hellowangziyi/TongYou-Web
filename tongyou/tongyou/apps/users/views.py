from django.shortcuts import render

# Create your views here
from django.views import View
from django.http import HttpResponse
from django.shortcuts import render

class RegisterView(View):
    # 注册
   def get(self, request):
        return render(request, 'register.html')