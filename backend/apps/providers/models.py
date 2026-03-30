from django.db import models

class PlatformAuth(models.Model):
    """
    模型用于统一存储从各平台代理授权（如 WeChat, Midea, Mijia 等）获取的三方认证凭证数据。
    """
    # 平台名称，如 'wechat', 'mijia', 'midea'
    platform_name = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="Platform Name")
    
    # 将包含不同结构的授权及身份配置均采用 JSON 格式进行保留
    auth_payload = models.JSONField(default=dict, blank=True, null=True, verbose_name="Auth Payload Data")
    
    # 标注当前配置是否仍处在一个可用的认证态下
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        db_table = "platform_auth"
        verbose_name = "Platform Auth"
        verbose_name_plural = "Platform Auths"

    def __str__(self):
        return f"{self.platform_name} (Active: {self.is_active})"
