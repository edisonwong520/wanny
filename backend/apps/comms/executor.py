import asyncio
import subprocess
from utils.logger import logger

class ShellExecutor:
    """
    针对通过微信收到的被 Manual-Gate 允许放行的复杂任务，
    执行底层的 `gemini -p ... --yolo` 调用，并收集其输出结果。
    """
    
    @classmethod
    async def execute_yolo(cls, shell_prompt: str) -> str:
        # 为了不阻塞主事件循环，使用 asyncio.to_thread 进行子进程调用
        logger.info(f"[Shell Executor] 正在子进程沙盒中拉起 Gemini CLI 执行指令: {shell_prompt}")
        
        # 建立完整的命令行调用：gemini -p "{prompt}" --yolo
        def _run_subprocess():
            try:
                # 屏蔽 sudo 前缀（简单的基础防御，具体依据未来 Docker 加固）
                if "sudo" in shell_prompt.lower():
                    return "🚫 高危拦截：禁止提权！由于包含 `sudo`，本指令不予放行。"
                
                cmd_args = ["uv", "run", "gemini", "-p", shell_prompt, "--yolo"]
                
                # capture_output 意味着拿到运行后的 stdout 和 stderr
                result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=120)
                
                out = result.stdout.strip()
                err = result.stderr.strip()
                
                ret_msg = f"✅ 执行完成！\n"
                if out:
                    # 避免过长的微信文本引起丢包，可以只保留截断的后文段
                    ret_msg += f"-- \n输出内容:\n{out[:800]}"
                if err:
                    ret_msg += f"\n--\n执行警告或报错:\n{err[:300]}"
                
                return ret_msg
                
            except subprocess.TimeoutExpired:
                return "⏱️ 任务执行超时！可能是被某交互卡住了。"
            except Exception as e:
                logger.error(f"[Shell Executor] 子进程崩毁外溢: {str(e)}")
                return f"❌ 内部严重执行报错：{str(e)}"
                
        return await asyncio.to_thread(_run_subprocess)
