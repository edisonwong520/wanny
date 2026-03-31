import json
from mijiaAPI import mijiaAPI, mijiaDevice, get_device_info
from utils.logger import logger

def test_capabilities():
    logger.info("初始化 Mijia API...")
    try:
        api = mijiaAPI()
        # 尝试静默登录（如果没有事先按之前的步骤成功扫码，这里会抛异常或需要终端扫码，但我们将它放在子进程中会有问题，最好此时已经登录）
        api.login()
        logger.info("登录成功（使用了本地缓存凭据）！")
    except Exception as e:
        logger.error(f"登录检查失败，可能未完成扫码授权: {e}")
        return

    logger.info("获取设备列表...")
    try:
        devices = api.get_devices_list()
        logger.info(f"成功获取到 {len(devices)} 个设备。正在检查它们的支持功能\n" + "="*100)
    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        return

    # 遍历当前账号下的设备，最多打印10个防止信息刷屏
    for device_raw in devices[:10]:
        dev_name = device_raw.get('name', 'Unknown')
        dev_model = device_raw.get('model', 'Unknown')
        logger.info(f"👉 设备名称: 【{dev_name}】 (Model: {dev_model})")
        
        try:
            # 1. 直接获取规格信息 (Spec) 打印关键可操作内容
            device_info = get_device_info(dev_model)
            if not device_info:
                logger.warning(f"  ❌ 无法获取设备 {dev_model} 的云端规范信息。")
                continue

            # 可控属性 (Properties)
            properties = device_info.get("properties", [])
            for prop in properties:
                prop_name = prop.get("name", "")
                prop_desc = prop.get("description", "")
                prop_type = prop.get("type", "")
                prop_rw = prop.get("rw", "")
                val_range = prop.get('range') or prop.get('value-list')
                range_str = f"范围/枚举: {val_range}" if val_range else ""
                
                # 'rw' 会是 'r', 'w', 'rw' 等
                if 'w' in prop_rw:
                    access_str = "读/写" if 'r' in prop_rw else "只写"
                    logger.info(f"    🔸 控制属性: {prop_name} ({prop_desc}) | 类型: {prop_type} | 权限: {access_str} | {range_str}")
                elif 'r' in prop_rw:
                    logger.info(f"    🔹 获取状态: {prop_name} ({prop_desc}) | 类型: {prop_type} | 权限: 只读")

            # 可触发动作 (Actions)
            actions = device_info.get("actions", [])
            for action in actions:
                action_name = action.get("name", "")
                action_desc = action.get("description", "")
                logger.info(f"    ⚡️ 动作执行: {action_name} ({action_desc}) (可以一键派发指令)")

            logger.info("-" * 40)
            
        except Exception as e:
            logger.error(f"  ❌ 分析提取设备 {dev_name} 功能时发生错误: {e}")

    if len(devices) > 10:
        logger.info(f"（省略剩余的 {len(devices) - 10} 个设备详情...）")
        
if __name__ == "__main__":
    test_capabilities()
