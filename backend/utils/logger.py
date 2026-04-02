import logging
import sys
from pathlib import Path

from utils.telemetry import TraceContextFilter

# 定义日志文件存放目录（默认在 backend/logs 下）
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

def setup_logger(name="wanny", level=logging.DEBUG):
    """
    统一封装的日志工厂函数
    """
    logger = logging.getLogger(name)
    
    # 如果已经存在 handlers，避免重复添加导致多次输出
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(level)

    # 核心要求：必须在日志中包含打印出处、文件名与所在行数 [%(filename)s:%(lineno)d]
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] [trace=%(trace_id)s span=%(span_id)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.addFilter(TraceContextFilter())
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出 Handler（附加 utf-8 编码避免中文乱码）
    file_handler = logging.FileHandler(LOGS_DIR / f"{name}.log", encoding='utf-8')
    file_handler.addFilter(TraceContextFilter())
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 停止向更上级的 logger 冒泡传递，避免冗余
    logger.propagate = False

    return logger

# 提供个全局单例直接引入使用：from utils.logger import logger
logger = setup_logger()

# 测试用例：在直接执行此文件时触发
if __name__ == "__main__":
    logger.info("日志系统初始化测试...")
    logger.debug("这是一条 Debug 消息，显示了具体调用所在的行数。")
    logger.error("这是一条 Error 测试消息！")
