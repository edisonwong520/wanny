import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from accounts.models import Account
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password

@csrf_exempt
def login_user(request):
    """
    用户登录接口 (POST)。
    校验邮箱与密码，成功则返回用户信息。
    """
    if request.method != "POST":
        return JsonResponse({"error": "仅支持 POST 请求"}, status=405)
    
    try:
        data = json.loads(request.body)
        identifier = data.get("identifier", data.get("email", "")).strip()
        password = data.get("password", "")
        
        if not identifier or not password:
            return JsonResponse({"error": "账号/邮箱和密码均为必填项"}, status=400)
            
        # 查找账户 (通过邮箱或昵称)
        from django.db.models import Q
        try:
            account = Account.objects.get(Q(email=identifier) | Q(name=identifier))
        except Account.DoesNotExist:
            return JsonResponse({"error": "账号或密码错误"}, status=401)
            
        # 校验密码
        if not check_password(password, account.password):
            return JsonResponse({"error": "邮箱或密码错误"}, status=401)
            
        return JsonResponse({
            "status": "success",
            "message": "登录成功",
            "data": {
                "id": account.id,
                "email": account.email,
                "name": account.name
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "无效的 JSON 数据"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"系统内部错误: {str(e)}"}, status=500)

@csrf_exempt
def register_user(request):
    """
    用户注册接口 (POST)。
    支持邮箱、姓名（账号）与密码注册。
    使用 Django 的哈希加密工具存储密码。
    """
    if request.method != "POST":
        return JsonResponse({"error": "仅支持 POST 请求"}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        name = data.get("name", "").strip()
        password = data.get("password", "")
        
        if not email or not name or not password:
            return JsonResponse({"error": "账号、邮箱、密码均为必填项"}, status=400)
            
        # 邮箱格式校验
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({"error": "邮箱格式不合法"}, status=400)
            
        # 密码强度检查 (示例)
        if len(password) < 6:
            return JsonResponse({"error": "密码长度不能少于 6 位"}, status=400)
            
        # 唯一性检查
        if Account.objects.filter(email=email).exists():
            return JsonResponse({"error": "该邮箱已被注册"}, status=400)
            
        # 创建账户，密码进行哈希
        account = Account.objects.create(
            email=email, 
            name=name,
            password=make_password(password)
        )
        
        return JsonResponse({
            "status": "success",
            "message": "注册成功",
            "data": {
                "id": account.id,
                "email": account.email,
                "name": account.name
            }
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "无效的 JSON 数据"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"系统内部错误: {str(e)}"}, status=500)
