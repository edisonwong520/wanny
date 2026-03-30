from django.db import models

class HomeMode(models.Model):
    """
    场景模式 (Home, Away, Sleep, Vacation 等)
    """
    name = models.CharField(max_length=50, unique=True, verbose_name="模式名称")
    is_active = models.BooleanField(default=False, verbose_name="是否激活")

    class Meta:
        db_table = "brain_home_mode"
        verbose_name = "Home Mode"
        verbose_name_plural = "Home Modes"

    def __str__(self):
        return f"{self.name} [{'ACTIVE' if self.is_active else 'INACTIVE'}]"

class HabitPolicy(models.Model):
    """
    权限矩阵表：规定了在特定模式下，特定设备、特定属性应该处于什么预期值。
    以及发生背离时，智能管家应该采取什么对策 (ASK / ALWAYS / NEVER)
    """
    class PolicyChoices(models.TextChoices):
        ASK = 'ASK', '主动询问'
        ALWAYS = 'ALWAYS', '总是直接执行'
        NEVER = 'NEVER', '从不执行(忽略)'

    mode = models.ForeignKey(HomeMode, on_delete=models.CASCADE, related_name="policies", verbose_name="所属模式")
    device_did = models.CharField(max_length=128, verbose_name="米家设备 ID")
    property = models.CharField(max_length=64, verbose_name="设备属性", help_text="例如 'power'")
    value = models.CharField(max_length=64, verbose_name="预期目标值", help_text="例如 'off'")
    policy = models.CharField(max_length=10, choices=PolicyChoices.choices, default=PolicyChoices.ASK, verbose_name="执行策略")

    class Meta:
        db_table = "brain_habit_policy"
        unique_together = ('mode', 'device_did', 'property') # 同一模式下同一设备的某个属性只能在表中拥有一条断言规则
        verbose_name = "Habit Policy"
        verbose_name_plural = "Habit Policies"

    def __str__(self):
        return f"{self.mode.name} -> {self.device_did}.{self.property}={self.value} [{self.policy}]"

class ObservationCounter(models.Model):
    """
    观察计数器：记录用户对特定询问的连续同意次数
    """
    policy = models.OneToOneField(HabitPolicy, on_delete=models.CASCADE, related_name="observation", verbose_name="绑定规则")
    success_count = models.IntegerField(default=0, verbose_name="连续同意(成功)次数")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="最后一次同意时间")

    class Meta:
        db_table = "brain_observation_counter"
        verbose_name = "Observation Counter"
        verbose_name_plural = "Observation Counters"

    def __str__(self):
        return f"Counter for {self.policy.device_did}: {self.success_count} success"
