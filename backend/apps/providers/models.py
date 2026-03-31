from django.db import models

class PlatformAuth(models.Model):
    """
    三方平台授权信息表。用于统一存储来自 WeChat、Mijia 等平台的认证凭证（Tokens, IDs），
    供系统在后台守护进程或异步 Task 中进行平台鉴权。
    """
    # 账户关联
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='platform_auths',
        null=True,
        blank=True,
        verbose_name="所属账户"
    )

    # 平台唯一名称标识，如 'wechat', 'mijia'
    platform_name = models.CharField(
        max_length=50, 
        db_index=True, 
        verbose_name="平台名称"
    )
    
    # 授权载荷数据：包含不同平台特有的 JSON 结构（如 access_token, user_id, base_url 等）
    auth_payload = models.JSONField(
        default=dict, 
        blank=True, 
        null=True, 
        verbose_name="授权数据载荷"
    )
    
    # 标注当前授权配置是否有效且处于激活态。若为 False，相关服务将停止心跳或监听。
    is_active = models.BooleanField(
        default=True, 
        verbose_name="是否激活"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "platform_auth"
        verbose_name = "三方平台授权"
        verbose_name_plural = "三方平台授权"

    def __str__(self):
        return f"{self.platform_name} (Active: {self.is_active})"
