from wechatbot import WeChatBot
from utils.logger import logger

# 初始化 iLink 微信 Bot 客户端
bot = WeChatBot()

@bot.on_message
async def handle(msg):
    """
    接收并处理微信消息
    """
    logger.info(f"🔔 收到微信消息 [{msg.user_id}]: {msg.text}")
    
    # 构建基础的 Echo 自动回复测试（可以在前面加上 AI 标签）
    if msg.text:
        reply_content = f"🤖 [Wanny 测试桩] 收到指令: {msg.text}"
        await bot.reply(msg, reply_content)
        logger.info(f"发送恢复成功: {reply_content}")

def test_wechat_bot():
    logger.info("🚀 正在初始化微信 iLink 客户端环境...")
    logger.info("稍后终端将输出【微信登录二维码】，请使用你的手机微信扫码授权登录。")
    logger.info("此架构基于微信协议进行长链接监听，请勿在同一机器高频登录。")
    
    try:
        # 该方法会自动拉起二维码、获取 Token 并在底层开启 WebSocket 挂起事件循环监听
        bot.run()
    except Exception as e:
        logger.error(f"❌ 微信模块发生致命错误: {e}")

if __name__ == "__main__":
    test_wechat_bot()
