from mijiaAPI import mijiaAPI, mijiaDevice
from utils.logger import logger

def test_turn_off_study_light():
    logger.info("初始化 Mijia API 凭据...")
    try:
        api = mijiaAPI()
        api.login()
    except Exception as e:
        logger.error(f"登录检查失败: {e}")
        return
    
    dev_name = "书房灯"
    logger.info(f"正在尝试连接目标设备: 【{dev_name}】...")
    
    try:
        device = mijiaDevice(api, dev_name=dev_name)
        
        # 先读取当前状态进行确认
        try:
            current_state = device.get('on')
            state_str = "已开启 🌕" if current_state else "已关闭 🌑"
            logger.info(f"当前状态探测: 【{dev_name}】目前为 {state_str}")
        except Exception:
            logger.warning("无法静默探查当前状态，仍将继续下发关灯指令。")

        logger.info(">>> 发送关灯控制指令 [on = False]...")
        
        # 此方法可修改设备的可写属性，将 on 置为 False 即为关闭设备
        device.set('on', False)
        
        # 再次获取以校验指令落地结果
        new_state = device.get('on')
        if not new_state:
            logger.info(f"✨ 控制成功！确认【{dev_name}】已成功关闭！")
        else:
            logger.warning("设备可能未及时响应或发生阻塞状态异常。")
            
    except Exception as e:
        logger.error(f"❌ 交互控制出现问题: {e}")

if __name__ == "__main__":
    test_turn_off_study_light()
