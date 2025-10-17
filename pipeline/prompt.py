#!/usr/bin/env python3
"""
prompt.py - 根据用户意图让Gemini API生成10字以内的prompt
根据用户意图采样结果让gemini api扮演用户生成相应类别的一个prompt
"""

import os
import requests
import json
from typing import Optional


class PromptGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """初始化prompt生成器"""
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("需要设置GEMINI_API_KEY环境变量")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': self.api_key
        }
        
        # 设置代理（如果需要）
        os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7890")
        os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
    
    def call_gemini(self, prompt: str) -> Optional[str]:
        """调用Gemini API"""
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 100}
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'candidates' in data and data['candidates']:
                    content = data['candidates'][0]['content']
                    if 'parts' in content and content['parts']:
                        return content['parts'][0]['text'].strip()
                    elif 'text' in content:
                        return content['text'].strip()
                else:
                    print(f"❌ Gemini API响应无候选结果: {data}")
            else:
                print(f"❌ Gemini API错误: {response.status_code} - {response.text}")
            return None
        except requests.exceptions.Timeout:
            print("❌ Gemini API超时")
            return None
        except requests.exceptions.ConnectionError:
            print("❌ Gemini API连接失败")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Gemini API请求异常: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            print(f"❌ Gemini API未知错误: {type(e).__name__}: {e}")
            return None
    
    def generate_prompt(self, intention: str) -> str:
        """根据用户意图生成10字以内的prompt"""
        # 构建系统prompt
        system_prompt = f"""
你是一个结构工程师，需要根据用户意图生成一个简洁的prompt。

用户意图类别：{intention}

请扮演用户，生成一个与该意图相关的、10字以内的简短prompt。
这个prompt应该：
1. 直接表达用户想要进行的结构分析任务
2. 语言简洁明了
3. 不超过10个字符（包括标点符号）
4. 符合中文表达习惯

示例：
- 如果意图是"内力反力"，可以生成："计算内力"、"求反力"、"内力分析"等
- 如果意图是"位移变形"，可以生成："计算位移"、"变形分析"、"位移结果"等  
- 如果意图是"模态分析"，可以生成："模态分析"、"振型计算"、"频率分析"等

请直接输出prompt，不要添加任何解释或引号。
"""
        
        response = self.call_gemini(system_prompt)
        if response:
            # 清理响应，确保不超过10个字符
            cleaned_response = response.strip().replace('"', '').replace("'", '')
            if len(cleaned_response) > 10:
                cleaned_response = cleaned_response[:10]
            return cleaned_response
        else:
            # 如果API调用失败，返回默认prompt
            return self._get_default_prompt(intention)
    
    def _get_default_prompt(self, intention: str) -> str:
        """获取默认prompt（当API调用失败时使用）"""
        default_prompts = {
            "内力反力": "计算内力",
            "位移变形": "计算位移", 
            "模态分析": "模态分析"
        }
        return default_prompts.get(intention, "结构分析")
    
    def generate_multiple_prompts(self, intention: str, count: int = 3) -> list:
        """为同一意图生成多个不同的prompt"""
        prompts = []
        for i in range(count):
            prompt = self.generate_prompt(intention)
            if prompt not in prompts:  # 避免重复
                prompts.append(prompt)
            if len(prompts) >= count:
                break
        
        # 如果生成的prompt不够，用默认的补充
        while len(prompts) < count:
            default_prompt = self._get_default_prompt(intention)
            if default_prompt not in prompts:
                prompts.append(default_prompt)
            else:
                break
        
        return prompts


def main():
    """测试函数"""
    print("=== Prompt生成器测试 ===")
    
    try:
        generator = PromptGenerator()
        
        # 测试三种用户意图
        intentions = ["内力反力", "位移变形", "模态分析"]
        
        for intention in intentions:
            print(f"\n用户意图: {intention}")
            prompt = generator.generate_prompt(intention)
            print(f"生成的prompt: '{prompt}' (长度: {len(prompt)})")
            
            # 测试生成多个prompt
            multiple_prompts = generator.generate_multiple_prompts(intention, 2)
            print(f"多个prompt: {multiple_prompts}")
            
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        print("请设置环境变量: export GEMINI_API_KEY='your-key'")
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    main()