from utils.logger import logger

class WeChatService:
    """
    负责封装与 WeChat Bot 相关的业务逻辑
    """
    
    @classmethod
    async def process_incoming_message(cls, message, bot):
        """
        处理由于微信号监听到的新消息，并做分发流转
        目前可对接至本地的智仆大脑分析
        """
        content = getattr(message, "content", "")
        # 后续可以加上消息类型的判断，如果是图片则怎么解析等
        logger.info(f"[WeChat Service] 开始处理业务路由，消息体内容: {content}")
        
        # ... 这里可以执行复杂的异步数据库查询、分析工作流等 ...
        
        # 准备统一的回包
        reply_content = f"系统已收到处理请求：{content[:10]}..."
        try:
            await bot.reply(message, reply_content)
            logger.info(f"[WeChat Service] 自动回复完成。")
        except Exception as e:
            logger.error(f"[WeChat Service] 自定义回复出错: {str(e)}")
