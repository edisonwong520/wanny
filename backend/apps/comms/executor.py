import asyncio
import subprocess
import time
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
                logger.debug(f"[Shell Executor] 进入沙盒执行函数。原始输入: {shell_prompt}")
                
                # 屏蔽 sudo 前缀
                if "sudo" in shell_prompt.lower():
                    logger.warning(f"[Shell Executor] 检测到高危指令 (sudo)，已拦截。")
                    return "🚫 高危拦截：禁止提权！由于包含 `sudo`，本指令不予放行。"
                
                cmd_args = ["gemini", "-p", shell_prompt, "--yolo"]
                logger.info(f"[Shell Executor] 正在拉起子进程: {' '.join(cmd_args)}")
                
                # capture_output 意味着拿到运行后的 stdout 和 stderr
                start_time = time.time()
                result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=120)
                duration = time.time() - start_time
                
                out = result.stdout.strip()
                err = result.stderr.strip()
                code = result.returncode

                # --- 核心清理逻辑：过滤掉 Gemini CLI 的初始化干扰日志 (MCP, YOLO, Credentials 等) ---
                def _clean_text(text: str) -> str:
                    clean_lines = []
                    ignore_keywords = [
                        "YOLO mode is enabled",
                        "Loaded cached credentials",
                        "Loading extension:",
                        "Scheduling MCP context refresh",
                        "All tool calls will be automatically approved",
                    ]
                    for line in text.splitlines():
                        if any(kw in line for kw in ignore_keywords):
                            continue
                        clean_lines.append(line)
                    return "\n".join(clean_lines).strip()

                out = _clean_text(out)
                err = _clean_text(err)

                logger.debug(f"[Shell Executor] 子进程执行结束。耗时: {duration:.2f}s, 返回码: {code}")
                logger.debug(f"[Shell Executor] STDOUT 长度: {len(out)}, STDERR 长度: {len(err)}")

                if out:
                    logger.debug(f"[Shell Executor] STDOUT 内容概要:\n{out[:200]}...")
                if err:
                    logger.warning(f"[Shell Executor] STDERR 内容概要:\n{err[:200]}...")

                status_emoji = "✅" if code == 0 else "⚠️"
                ret_msg = f"{status_emoji} 执行完成！{'' if code == 0 else f'(Code: {code})'}\n"
                
                if out:
                    ret_msg += f"-- \n输出内容:\n{out[:800]}"
                else:
                    ret_msg += f"-- \n(命令执行成功，无标准输出内容)"

                if err:
                    ret_msg += f"\n--\n执行警告或报错:\n{err[:300]}"
                
                return ret_msg
                
            except subprocess.TimeoutExpired:
                logger.error(f"[Shell Executor] 任务执行超时 (120s)")
                return "⏱️ 任务执行超时！可能是被某交互卡住了。"
            except Exception as e:
                logger.error(f"[Shell Executor] 子进程崩毁外溢: {str(e)}", exc_info=True)
                return f"❌ 内部执行报错：{str(e)}"
                
        return await asyncio.to_thread(_run_subprocess)
