import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from accounts.models import Account
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password, check_password
from accounts.auth import create_account_token


def _error(message: str, status: int, *, code: str | None = None):
    payload = {"error": message}
    if code:
        payload["error_code"] = code
    return JsonResponse(payload, status=status)


@csrf_exempt
def login_user(request):
    """
    用户登录接口 (POST)。
    校验邮箱与密码，成功则返回用户信息。
    """
    if request.method != "POST":
        return _error("仅支持 POST 请求", 405, code="method_not_allowed")
    
    try:
        data = json.loads(request.body)
        identifier = data.get("identifier", data.get("email", "")).strip()
        password = data.get("password", "")
        
        if not identifier or not password:
            return _error("账号/邮箱和密码均为必填项", 400, code="missing_login_fields")
            
        # 查找账户 (通过邮箱或昵称)
        from django.db.models import Q
        try:
            account = Account.objects.get(Q(email=identifier) | Q(name=identifier))
        except Account.DoesNotExist:
            return _error("账号或密码错误", 401, code="invalid_credentials")
            
        # 校验密码
        if not check_password(password, account.password):
            return _error("邮箱或密码错误", 401, code="invalid_credentials")
            
        return JsonResponse({
            "status": "success",
            "message": "登录成功",
            "data": {
                "id": account.id,
                "email": account.email,
                "name": account.name,
                "token": create_account_token(account),
            }
        })
        
    except json.JSONDecodeError:
        return _error("无效的 JSON 数据", 400, code="invalid_json")
    except Exception as e:
        return _error(f"系统内部错误: {str(e)}", 500, code="internal_error")

@csrf_exempt
def register_user(request):
    """
    用户注册接口 (POST)。
    支持邮箱、姓名（账号）与密码注册。
    使用 Django 的哈希加密工具存储密码。
    """
    if request.method != "POST":
        return _error("仅支持 POST 请求", 405, code="method_not_allowed")
    
    try:
        data = json.loads(request.body)
        email = data.get("email", "").strip()
        name = data.get("name", "").strip()
        password = data.get("password", "")
        
        if not email or not name or not password:
            return _error("账号、邮箱、密码均为必填项", 400, code="missing_register_fields")
            
        # 邮箱格式校验
        try:
            validate_email(email)
        except ValidationError:
            return _error("邮箱格式不合法", 400, code="invalid_email")
            
        # 密码强度检查 (示例)
        if len(password) < 6:
            return _error("密码长度不能少于 6 位", 400, code="password_too_short")
            
        # 唯一性检查
        if Account.objects.filter(email=email).exists():
            return _error("该邮箱已被注册", 400, code="duplicate_email")
        if Account.objects.filter(name=name).exists():
            return _error("该昵称已被使用", 400, code="duplicate_name")
            
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
                "name": account.name,
                "token": create_account_token(account),
            }
        }, status=201)
        
    except json.JSONDecodeError:
        return _error("无效的 JSON 数据", 400, code="invalid_json")
    except Exception as e:
        return _error(f"系统内部错误: {str(e)}", 500, code="internal_error")
