from mijiaAPI import mijiaAPI, mijiaDevice
from utils.logger import logger

def test_reset_pet_fountain_filter():
    logger.info("初始化 Mijia API 凭据...")
    try:
        api = mijiaAPI()
        api.login()
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return
    
    dev_name = "Mijia Smart Pet Fountain 2"
    logger.info(f"正在尝试连接目标设备: 【{dev_name}】...")
    
    try:
        # 封装设备抽象类，它会自动处理 siid 和 piid 的匹配
        device = mijiaDevice(api, dev_name=dev_name)
        
        # 顺便获取一下当前的滤芯寿命作为执行前的对比
        try:
            current_life = device.get('filter-life-level')
            current_time = device.get('filter-left-time')
            logger.info(f"执行前状态 - 滤芯剩余寿命: {current_life}% | 剩余可用时间: {current_time}天")
        except Exception:
            logger.warning("无法读取执行前状态，仍将继续下发重置指令。")

        logger.info(">>> 开始向设备下发 [reset-filter-life] 重置滤芯动作指令...")
        
        # 派发重置动作
        result = device.run_action('reset-filter-life')
        logger.info(f"指令下发响应结果: {result}")
        
        logger.info("🎉 滤芯重置成功！建议打开米家 APP 确认该饮水机滤芯是否已恢复 100%。")
    except Exception as e:
        logger.error(f"❌ 交互失败: {e}")

if __name__ == "__main__":
    test_reset_pet_fountain_filter()
