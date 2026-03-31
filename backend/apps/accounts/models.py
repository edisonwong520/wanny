from django.db import models

class Account(models.Model):
    """
    轻量级账户模型。仅记录注册邮箱与姓名，跳过 Django 原生 auth.User 体系。
    """
    # 注册邮箱，作为唯一识别符
    email = models.EmailField(
        max_length=255, 
        unique=True, 
        db_index=True, 
        verbose_name="用户邮箱"
    )
    
    # 用户姓名 (账号)，由于 AI 称呼
    name = models.CharField(
        max_length=100, 
        verbose_name="用户姓名/账号"
    )
    
    # 密码 (存储哈希后的值)
    password = models.CharField(
        max_length=128,
        default="",
        verbose_name="账户密码",
        help_text="仅存储 PBKDF2 或 Argon2 哈希后的密文"
    )
    
    # 账户创建与最后更新时间
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "accounts_account"
        ordering = ['-created_at']
        verbose_name = "个人账户"
        verbose_name_plural = "个人账户"

    def __str__(self):
        return f"{self.name} <{self.email}>"
