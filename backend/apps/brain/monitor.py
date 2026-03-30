import time
import asyncio
from asgiref.sync import sync_to_async
from utils.logger import logger
from brain.models import HomeMode, HabitPolicy, ObservationCounter
from comms.models import PendingCommand

class MonitorService:
    @classmethod
    async def loop_start(cls, bot):
        """
        纯异步死循环入口，与 WeChat 事件循环共生。
        """
        logger.info("[Brain Monitor] 开启后台家室传感器定时轮询守护模式！")
        while True:
            try:
                # 每 30 秒一瞥
                await asyncio.sleep(30)
                await cls._poll_and_judge(bot)
            except Exception as e:
                logger.error(f"[Brain Monitor] 长青循环崩坏: {str(e)}")
                await asyncio.sleep(30)

    @classmethod
    async def _poll_and_judge(cls, bot):
        # 1. 尝试寻找当前系统中活跃的 Mode 
        active_mode = await sync_to_async(HomeMode.objects.filter(is_active=True).first)()
        if not active_mode:
            return # 当家宅无明确状态标示时休眠
            
        # 2. 从米家抓取所有的实际设备状态
        # (在此处做逻辑封装：因未实现真实网络交互我们在此造出假设设备离家时还开着)
        # 例如你调用 mijiaApi.get_device_list() 获取全量 dict
        current_devices_status = {
            "mocked_light_001": {"power": "on"}, 
            "mocked_ac_002": {"power": "off"}
        }

        # 3. 拿出当前 Mode 应该遵守的所有纪律
        policies = await sync_to_async(list)(HabitPolicy.objects.filter(mode=active_mode))
        
        for rule in policies:
            dev_id = rule.device_did
            prop_key = rule.property
            t_value = rule.value

            real_val = current_devices_status.get(dev_id, {}).get(prop_key, "unknown")
            if real_val == t_value or real_val == "unknown":
                continue # 数据相符，或并未抓出，跳过
                
            # 走到这里意味着【环境出现悖离了】！如：要求离家关灯，但灯测出来仍是 on !
            
            if rule.policy == 'NEVER':
                # 我们不允许动，直接无视
                continue
                
            elif rule.policy == 'ALWAYS':
                # 我们拥有直属授权，果断斩除异常，如默默调用底层 API
                logger.info(f"[Brain Hook] 获取了直接斩杀权！自动静默调控 {dev_id} {prop_key} -> {t_value}。")
                # (mock call to mijia to set property)
                continue
                
            elif rule.policy == 'ASK':
                # 如果我们没有永久权，就需要询问了!
                # 构建话术，根据之前的容忍计数器决定采用强硬转正语句还是委婉请示
                obs, _ = await sync_to_async(ObservationCounter.objects.get_or_create)(policy=rule)
                
                # 为了防止狂发垃圾消息，看看是否该设备在这个指令要求下已发过 PendingCommand 并还未执行完
                already_asked = await sync_to_async(PendingCommand.objects.filter(
                    original_prompt__icontains=f"[MIJIA:{dev_id}]",
                    is_approved=False,
                    is_executed=False
                ).exists)()

                if already_asked:
                    continue  # 别问了等回复呢

                msg = f"检测到在 {active_mode.name} 时，您的 {dev_id} 设备还在开着。"
                
                if obs.success_count >= 3:
                    msg = "Sir，" + msg + f"\n我已经连续帮您关了 {obs.success_count} 次，建议您这次回复“以后直接关”来让我永久自动接管好吗？"
                else:
                    msg = "Sir，" + msg + "\n是否需要我现在关闭它？（您可以回复 同意/拒绝）"

                new_pending = await sync_to_async(PendingCommand.objects.create)(
                    # 先留存一条没绑定 user_id 的占位，实际发送时我们通过 bot 匹配正确的微信联系人。
                    user_id="BROADCAST", 
                    original_prompt=f"[MIJIA:{dev_id}] 想变更 {prop_key} 为 {t_value}！",
                    shell_command="", 
                )

                # 将这条请求推送给微信去：
                # 这里我们利用由于之前在微信上与 Bot 说过话所以留存下的上下文 Context Token 发送。
                logger.warning(f"[主动推送给主人] ==============> \n{msg}\n")
                if not bot or not getattr(bot, '_context_tokens', None):
                    continue

                for wx_user_id in list(bot._context_tokens.keys()):
                    try:
                        await bot.send(wx_user_id, msg)
                        # 同时将 pending 的确切归属人更新，使得将来他回复时能匹配上
                        new_pending.user_id = wx_user_id
                        await sync_to_async(new_pending.save)()
                    except Exception as e:
                        logger.error(f"推送至微信 {wx_user_id} 失败：{e}")
