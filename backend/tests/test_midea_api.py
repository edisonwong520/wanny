import os
import uuid
import time
import requests
from dotenv import load_dotenv

# 使用相对路径或正确路径引入 logger
import sys
# 确保可以将 backend 目录纳入 sys.path，以便引入 utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.logger import logger

# 提前加载 .env 到环境变量
load_dotenv()

class MideaOAuth2Client:
    """
    美的(Midea) IoT 平台 Cloud-to-Cloud API (v2) 客户端验证
    参考: https://iot.midea.com/docs/control-midea-cloud-devices/cloud-2-cloud-v2-api.html
    """
    
    BASE_URL = "https://api-prod.smartmidea.net"
    
    def __init__(self):
        # 强制从 .env 获取应用凭证，避免硬编码
        self.client_id = os.getenv("MIDEA_CLIENT_ID")
        self.client_secret = os.getenv("MIDEA_CLIENT_SECRET")
        self.redirect_uri = os.getenv("MIDEA_REDIRECT_URI", "https://localhost/callback")
        
        # 为了测试方便，也可以直接在 .env 里提供已获取到的 code 或 token
        self.access_token = os.getenv("MIDEA_ACCESS_TOKEN", "")

        if not self.client_id or not self.client_secret:
            logger.warning("[Midea API Test] .env 文件中未配置 MIDEA_CLIENT_ID 或 MIDEA_CLIENT_SECRET")

    def get_authorize_url(self) -> str:
        """
        第一步: 获取用户授权登录页面 URL (OAuth 2.0 - response_type=code)
        """
        if not self.client_id or not self.redirect_uri:
            logger.error("[Midea API Test] 缺失 client_id 或 redirect_uri 无法生成授权链接。")
            return ""
        
        # 组装授权 URL
        url = f"{self.BASE_URL}/v2/open/oauth2/authorize"
        params = [
            f"client_id={self.client_id}",
            "state=1",
            "response_type=code",
            f"redirect_uri={self.redirect_uri}"
        ]
        authorize_url = f"{url}?{'&'.join(params)}"
        logger.info(f"[Midea API Test] 成功生成用户授权授权链接: {authorize_url}")
        return authorize_url

    def get_token(self, auth_code: str) -> dict:
        """
        第二步: 使用用户登录后回调附带的 code，换取 AccessToken
        """
        url = f"{self.BASE_URL}/v2/open/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": auth_code
        }
        
        logger.info("[Midea API Test] 正在使用 authorization_code 换取令牌...")
        try:
            # 官方文档标注参数格式：body参数 (JSON)
            response = requests.post(url, json=payload, timeout=10)
            res_json = response.json()
            if "error" in res_json:
                logger.error(f"[Midea API Test] 令牌获取失败: {res_json}")
            else:
                self.access_token = res_json.get("access_token")
                logger.info("[Midea API Test] 令牌获取成功！")
            return res_json
        except Exception as e:
            logger.error(f"[Midea API Test] 请求 get_token 时发生异常: {e}")
            return {}

    def get_device_list(self) -> dict:
        """
        第三步: 获取用户设备列表 (测试接口连通性)
        """
        if not self.access_token:
            logger.error("[Midea API Test] Access token 为空，需要先完成授权获取 Token。")
            return {}

        url = f"{self.BASE_URL}/v2/open/device/list/get"
        
        # 按照 OAuth2 标准将 Token 放入 Header，部分 IoT 厂商也会要求放在 query 或 body 中，此处提供标准的 Bearer Token 请求头
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # 文档要求 reqId 长度32位组成
        req_id = str(uuid.uuid4()).replace("-", "")
        # stamp 为13位或毫秒的时间戳
        stamp = str(int(time.time() * 1000))
        
        payload = {
            "reqId": req_id,
            "stamp": stamp
        }

        logger.info(f"[Midea API Test] 正在获取设备列表 (ReqId: {req_id})...")
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            res_json = response.json()
            if "error" in res_json:
                logger.error(f"[Midea API Test] 获取设备列表失败: {res_json}")
            else:
                logger.info(f"[Midea API Test] 设备列表获取成功: {res_json}")
            return res_json
        except Exception as e:
            logger.error(f"[Midea API Test] 请求 get_device_list 时发生异常: {e}")
            return {}

def test_midea_flow():
    """
    执行测试验证流
    """
    logger.info("========== 美的 IoT API 可行性测试开始 ==========")
    
    client = MideaOAuth2Client()
    
    # 打印授权链接，供开发者手动复制去浏览器中打开并登录
    authorize_url = client.get_authorize_url()
    logger.info("======================================================")
    logger.info("【步骤一】请在浏览器中打开以下链接，完成美的账号登录并授权:")
    logger.info(f"🔗 {authorize_url}")
    logger.info("登录成功后，浏览器会重定向回回调地址，并在 URL 提供 code 参数.")
    logger.info("======================================================")
    
    auth_code = os.getenv("MIDEA_AUTH_CODE")
    if not auth_code and not client.access_token:
        logger.warning("[Midea API Test] 当前 .env 缺少 MIDEA_AUTH_CODE 参数，"
                       "请将上一步浏览器获取到的 code=XXX 填入 .env 中: MIDEA_AUTH_CODE=your_code_here，然后重新运行该脚本。")
        return
    
    # 如果还没有 token 但有 code，去换 token
    if not client.access_token and auth_code:
        client.get_token(auth_code)
        
    # 如果已经有 token(或者刚换取成功)，测试获取设备列表
    if client.access_token:
        logger.info("[Midea API Test] 检测到 Access Token，尝试拉取设备列表以验证完整状态...")
        client.get_device_list()
        
    logger.info("========== 美的 IoT API 可行性测试结束 ==========")

if __name__ == "__main__":
    test_midea_flow()
