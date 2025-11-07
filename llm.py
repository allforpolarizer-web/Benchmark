import os
import time
import requests
from typing import Optional

# 设置代理（如果需要）
# HTTP/HTTPS 代理（Clash 常见端口 7890）
if not os.getenv('HTTP_PROXY') and not os.getenv('HTTPS_PROXY'):
    os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7890")
    os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None, status_callback=None, base_url: Optional[str] = None, timeout: int = 60, max_retries: int = 3):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("需要设置GEMINI_API_KEY环境变量")

        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        }
        self.timeout = timeout
        self.status_callback = status_callback or (lambda *args, **kwargs: None)
        self.max_retries = max(1, int(max_retries))

    def call(self, prompt: str) -> Optional[str]:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 20000}
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    # 不打印原始响应，直接解析
                    if 'candidates' in data and data['candidates']:
                        content = data['candidates'][0]['content']
                        if 'parts' in content and content['parts']:
                            return content['parts'][0]['text']
                        elif 'text' in content:
                            return content['text']
                        # 无可用内容
                        return None
                    else:
                        # 响应结构异常，终止重试
                        return None
                else:
                    # 仅对5xx错误进行重试；4xx为客户端错误不重试
                    if 500 <= response.status_code < 600 and attempt < self.max_retries:
                        time.sleep(min(2 ** attempt, 8))
                        continue
                    print(f"❌ Gemini API错误: {response.status_code} - {response.text}")
                    return None
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                # 超时或网络错误：重试
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                # 最后一次仍失败
                print("❌ Gemini API超时或连接失败")
                return None
            except requests.exceptions.RequestException as e:
                print(f"❌ Gemini API请求异常: {type(e).__name__}: {e}")
                return None
            except Exception as e:
                print(f"❌ Gemini API未知错误: {type(e).__name__}: {e}")
                return None

        return None




