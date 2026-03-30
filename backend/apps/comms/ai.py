import os
import json
import asyncio
from openai import AsyncOpenAI
from google import genai
from google.genai import types
from utils.logger import logger

class AIAgent:
    """
    统一的 AI 客户端封装，支持原生的 Gemini API 协议或任何兼容 OpenAI 的代理地址。
    根据环境变量自动选择基础实现。
    """
    def __init__(self):
        # 官方 Gemini 配置
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        # Open-AI 兼容后端配置
        self.base_url = os.getenv("AI_BASE_URL")
        self.api_key = os.getenv("AI_API_KEY")
        self.model = os.getenv("AI_MODEL", "gpt-4o")

        # 优先级：GEMINI_API_KEY > AI_BASE_URL+AI_API_KEY
        if self.gemini_api_key:
            self.provider = "gemini"
            self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            logger.info(f"[AI Agent] 初始化完成，驱动源为原生 Google GenAI SDK (model={self.gemini_model_name})")
        elif self.base_url and self.api_key:
            self.provider = "openai"
            self._openai_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"[AI Agent] 初始化完成，驱动源为 OpenAI Compatible 协议 ({self.base_url}, model={self.model})")
        else:
            self.provider = "none"
            logger.warning("[AI Agent] 未检测到有效的 AI 配置参数 (GEMINI_API_KEY 或 AI_API_KEY)。")

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        根据当前初始化的客户端执行推理，强制要求返回 JSON 对象结构，最终转化并返回 dict。
        """
        if self.provider == "none":
            return {"type": "simple", "response": "[系统提示] 开发者尚未在 .env 中正确配置模型路由。"}
            
        content = ""
        try:
            if self.provider == "openai":
                response = await self._openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt.strip()},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                content = response.choices[0].message.content.strip()
            
            elif self.provider == "gemini":
                # 利用 Thread 规避同步阻塞，或使用新的 aio.models
                def _run_gemini():
                    res = self._gemini_client.models.generate_content(
                        model=self.gemini_model_name,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt.strip(),
                            response_mime_type="application/json"
                        )
                    )
                    return res.text.strip()
                content = await asyncio.to_thread(_run_gemini)
                
            # 清理可能附带的 markdown 格式头尾
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            return json.loads(content.strip())
            
        except json.JSONDecodeError as e:
            logger.error(f"[AI Agent] 模型没有返回合规 JSON，原文: {content}, 错误: {e}")
            return {"type": "simple", "response": "[系统报错] 模型没有正确返回 JSON 格式，意图解析失败。"}
        except Exception as e:
            logger.error(f"[AI Agent] {self.provider} 请求发生异常: {str(e)}")
            return {"type": "simple", "response": f"[系统报错] 大脑管线离线异常：{str(e)}"}


async def analyze_intent(user_msg: str) -> dict:
    """
    向外暴露的快速意图分析接口。
    """
    default_system_prompt = """
    你是 Wanny (Classic Jarvis)，一位专业、礼貌的智能管家。用户的消息可能包含对话、指令或对你之前提议的反馈。请根据上下文，分析用户的回复意图并严格返回 JSON 对象。
    
    意图分类如下：
    1. `CHAT`: 普通的闲聊、问候、或者查询等可以直接通识回答的问题。
    2. `COMPLEX_SHELL`: 用户要求你执行诸如写文件、深度网络执行、下载等需要在宿主机环境执行的系统级复杂指令（不要带有危及底层系统的命令如sudo）。
    3. `CONFIRM`: 针对你之前的拦截提问（比如是否操作某设备，是否执行某指令），用户做出了单次的肯定答复（如：好的、同意、批准、关吧、麻烦你了）。
    4. `PERMANENT_ALLOW`: 用户不但同意了你的提问，还主动表达了“一劳永逸”或“永久授权”的意向（如：以后都这样、以后你自己弄就行、以后直接关）。
    5. `DENY`: 用户拒绝了你的提问或操作（如：不要、先别关、不批准、取消）。

    必须严格返回纯 JSON 对象（不要使用 Markdown `json` 块），格式规范：
    {
      "type": "CHAT",          // 一定要是 CHAT, COMPLEX_SHELL, CONFIRM, PERMANENT_ALLOW, DENY 这五个字符串之一
      "response": "仅当类型为 CHAT 或 DENY 时，用来直接回复用户的话术。Jarvis风格",
      "shell_prompt": "仅 COMPLEX_SHELL 需要填写，向底壳传递的具体任务执行要求",
      "confirm_text": "仅 COMPLEX_SHELL 需要填写，发给用户请求人工同意的提示语"
    }
    """
    
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", default_system_prompt)
    agent = AIAgent()
    return await agent.generate_json(system_prompt, user_msg)
