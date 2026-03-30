import os
import json
import asyncio
from openai import AsyncOpenAI
import google.generativeai as genai
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

        if self.base_url and self.api_key:
            self.provider = "openai"
            self._openai_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"[AI Agent] 初始化完成，驱动源为 OpenAI Compatible 协议 ({self.base_url})")
        elif self.gemini_api_key:
            self.provider = "gemini"
            genai.configure(api_key=self.gemini_api_key)
            logger.info(f"[AI Agent] 初始化完成，驱动源为原生 Google Gemini SDK")
        else:
            self.provider = "none"
            logger.warning("[AI Agent] 未检测到有效的 AI 配置参数 (AI_API_KEY 或 GEMINI_API_KEY)。")

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
                # Google 生成模型不支持完全原生的 Asyncio 支持，利用 Thread 规避阻塞
                def _run_gemini():
                    # gemini SDK >= 0.8 支持在构造处传递 system_instruction
                    model_inst = genai.GenerativeModel(
                        model_name=self.gemini_model_name,
                        system_instruction=system_prompt.strip(),
                        generation_config={"response_mime_type": "application/json"}
                    )
                    res = model_inst.generate_content(user_prompt)
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
    你是 Wanny AI Agent (Jarvis Shell)，一位干练的智能管家。用户的指示将被分为两类任务：
    1. 简单询问 (Simple Queries)：针对普通的聊天、常识询问等，你直接生成回复文本，不需要动用本地系统能力。
    2. 复杂任务 (Complex Tasks)：当请求涉及联网深度搜索、处理本地文件、下载执行等高危险或需要极强行动力的操作时，你**必须**输出一段传递给底层 gemini CLI 的明确执行要求 Prompt（此 prompt 必须直接可用，绝不能包含危险词汇如 sudo 等）。

    必须严格返回纯 JSON 对象（不要使用 Markdown `json` 块包裹包裹），格式定义：
    【如果为简单询问】
    {
      "type": "simple",
      "response": "针对问题的完整直接回答"
    }
    【如果为复杂任务】
    {
      "type": "complex",
      "shell_prompt": "告诉底层执行器要怎么做，例如：抓取今天上海的最详细天气预报",
      "confirm_text": "Sir, 请问是否批准我执行此复杂任务：..."
    }
    """
    
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT", default_system_prompt)
    agent = AIAgent()
    return await agent.generate_json(system_prompt, user_msg)
