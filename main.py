from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import asyncio
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Any
import aiohttp
import hashlib
import os

@register("qq_telegram_summarizer", "AI助手", "QQ群消息监听与AI总结Telegram推送插件", "1.0.0")
class QQTelegramSummarizerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.message_cache: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.last_summary_time: Dict[str, datetime] = {}
        self.config = {
            'message_threshold': 50,  # 消息阈值
            'time_window_hours': 2,   # 时间窗口（小时）
            'telegram_bot_token': '',  # Telegram Bot Token
            'telegram_chat_id': '',    # Telegram Chat ID
            'ai_api_url': 'https://api.openai.com/v1/chat/completions',  # AI API地址
            'ai_api_key': '',         # AI API密钥
            'ai_model': 'gpt-3.5-turbo',  # AI模型
            'target_groups': [],      # 监听的QQ群列表，为空则监听所有群
            'summary_prompt': '请总结以下QQ群聊天记录的主要话题和重点内容，用简洁的中文回复：\n\n{messages}'
        }
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        config_path = os.path.join(self.context.base_path, 'qq_telegram_config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                    logger.info("配置文件加载成功")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    
    def save_config(self):
        """保存配置文件"""
        config_path = os.path.join(self.context.base_path, 'qq_telegram_config.json')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.info("配置文件保存成功")
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    async def initialize(self):
        """插件初始化"""
        logger.info("QQ群消息监听与AI总结Telegram推送插件初始化完成")
        if not all([self.config['telegram_bot_token'], self.config['telegram_chat_id'], self.config['ai_api_key']]):
            logger.warning("请使用 /qtconfig 命令配置必要的参数")
    
    @filter.group_message
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息"""
        try:
            group_id = event.group_id if hasattr(event, 'group_id') else str(event.platform_meta.get('group_id', 'unknown'))
            
            # 如果配置了特定群组，只监听这些群组
            if self.config['target_groups'] and group_id not in self.config['target_groups']:
                return
            
            user_name = event.get_sender_name()
            message_str = event.message_str
            timestamp = datetime.now()
            
            # 存储消息到缓存
            message_data = {
                'user': user_name,
                'message': message_str,
                'time': timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.message_cache[group_id].append(message_data)
            
            # 检查是否需要生成总结
            await self.check_and_summarize(group_id)
            
        except Exception as e:
            logger.error(f"处理群消息时出错: {e}")
    
    async def check_and_summarize(self, group_id: str):
        """检查是否达到总结条件"""
        try:
            messages = list(self.message_cache[group_id])
            if len(messages) < self.config['message_threshold']:
                return
            
            # 检查时间窗口
            now = datetime.now()
            last_summary = self.last_summary_time.get(group_id)
            
            if last_summary and (now - last_summary).total_seconds() < self.config['time_window_hours'] * 3600:
                return
            
            # 筛选时间窗口内的消息
            cutoff_time = now - timedelta(hours=self.config['time_window_hours'])
            recent_messages = []
            
            for msg in messages:
                msg_time = datetime.strptime(msg['time'], '%Y-%m-%d %H:%M:%S')
                if msg_time >= cutoff_time:
                    recent_messages.append(msg)
            
            if len(recent_messages) >= self.config['message_threshold']:
                # 检查LLM和Telegram配置
                if self.config['use_internal_llm']:
                    provider = self.context.get_using_provider()
                    if not provider:
                        logger.warning("LLM提供商未配置，无法生成总结")
                        return
                
                if not all([self.config['telegram_bot_token'], self.config['telegram_chat_id']]):
                    logger.warning("Telegram配置不完整，无法发送消息")
                    return
                    
                await self.generate_and_send_summary(group_id, recent_messages)
                self.last_summary_time[group_id] = now
                
        except Exception as e:
            logger.error(f"检查和总结消息时出错: {e}")
    
    async def generate_and_send_summary(self, group_id: str, messages: List[Dict]):
        """生成AI总结并发送到Telegram"""
        try:
            # 格式化消息
            formatted_messages = []
            for msg in messages[-self.config['message_threshold']:]:  # 取最新的N条消息
                formatted_messages.append(f"[{msg['time']}] {msg['user']}: {msg['message']}")
            
            messages_text = '\n'.join(formatted_messages)
            
            # 调用AI API生成总结
            summary = await self.get_ai_summary(messages_text)
            
            if summary:
                # 发送到Telegram
                await self.send_to_telegram(group_id, summary, len(messages))
                logger.info(f"群 {group_id} 的消息总结已发送到Telegram")
            
        except Exception as e:
            logger.error(f"生成和发送总结时出错: {e}")
    
    async def get_ai_summary(self, messages_text: str) -> str:
        """调用AI API获取总结"""
        try:
            headers = {
                'Authorization': f'Bearer {self.config["ai_api_key"]}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.config['ai_model'],
                'messages': [{
                    'role': 'user',
                    'content': self.config['summary_prompt'].format(messages=messages_text)
                }],
                'max_tokens': 500,
                'temperature': 0.7
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config['ai_api_url'], headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content'].strip()
                    else:
                        logger.error(f"AI API请求失败: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"调用AI API时出错: {e}")
            return None
    
    async def send_to_telegram(self, group_id: str, summary: str, message_count: int):
        """发送消息到Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.config['telegram_bot_token']}/sendMessage"
            
            text = f"📊 QQ群 {group_id} 消息总结\n\n"
            text += f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            text += f"💬 消息数量: {message_count} 条\n\n"
            text += f"📝 AI总结:\n{summary}"
            
            data = {
                'chat_id': self.config['telegram_chat_id'],
                'text': text,
                'parse_mode': 'HTML'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status != 200:
                        logger.error(f"发送Telegram消息失败: {response.status}")
                        
        except Exception as e:
            logger.error(f"发送Telegram消息时出错: {e}")
    
    @filter.command("qtconfig")
    async def config_command(self, event: AstrMessageEvent):
        """配置命令"""
        args = event.message_str.strip().split()[1:] if len(event.message_str.strip().split()) > 1 else []
        
        if not args:
            config_text = "当前配置:\n"
            config_text += f"消息阈值: {self.config['message_threshold']}\n"
            config_text += f"时间窗口: {self.config['time_window_hours']} 小时\n"
            config_text += f"Telegram Bot Token: {'已设置' if self.config['telegram_bot_token'] else '未设置'}\n"
            config_text += f"Telegram Chat ID: {'已设置' if self.config['telegram_chat_id'] else '未设置'}\n"
            config_text += f"AI API Key: {'已设置' if self.config['ai_api_key'] else '未设置'}\n"
            config_text += f"目标群组: {self.config['target_groups'] or '所有群组'}\n\n"
            config_text += "使用方法:\n"
            config_text += "/qtconfig threshold <数字> - 设置消息阈值\n"
            config_text += "/qtconfig window <小时数> - 设置时间窗口\n"
            config_text += "/qtconfig telegram_token <token> - 设置Telegram Bot Token\n"
            config_text += "/qtconfig telegram_chat <chat_id> - 设置Telegram Chat ID\n"
            config_text += "/qtconfig ai_key <api_key> - 设置AI API密钥\n"
            config_text += "/qtconfig groups <群号1,群号2> - 设置监听群组（逗号分隔）\n"
            yield event.plain_result(config_text)
            return
        
        if len(args) >= 2:
            key = args[0]
            value = ' '.join(args[1:])
            
            if key == 'threshold':
                try:
                    self.config['message_threshold'] = int(value)
                    self.save_config()
                    yield event.plain_result(f"消息阈值已设置为: {value}")
                except ValueError:
                    yield event.plain_result("请输入有效的数字")
            
            elif key == 'window':
                try:
                    self.config['time_window_hours'] = int(value)
                    self.save_config()
                    yield event.plain_result(f"时间窗口已设置为: {value} 小时")
                except ValueError:
                    yield event.plain_result("请输入有效的小时数")
            
            elif key == 'telegram_token':
                self.config['telegram_bot_token'] = value
                self.save_config()
                yield event.plain_result("Telegram Bot Token已设置")
            
            elif key == 'telegram_chat':
                self.config['telegram_chat_id'] = value
                self.save_config()
                yield event.plain_result("Telegram Chat ID已设置")
            
            elif key == 'ai_key':
                self.config['ai_api_key'] = value
                self.save_config()
                yield event.plain_result("AI API密钥已设置")
            
            elif key == 'groups':
                groups = [g.strip() for g in value.split(',') if g.strip()]
                self.config['target_groups'] = groups
                self.save_config()
                yield event.plain_result(f"监听群组已设置为: {groups}")
            
            else:
                yield event.plain_result("未知的配置项")
        else:
            yield event.plain_result("参数不足")
    
    @filter.command("qtstatus")
    async def status_command(self, event: AstrMessageEvent):
        """查看状态"""
        status_text = "📊 插件状态:\n\n"
        
        for group_id, messages in self.message_cache.items():
            status_text += f"群 {group_id}:\n"
            status_text += f"  缓存消息数: {len(messages)}\n"
            last_summary = self.last_summary_time.get(group_id)
            if last_summary:
                status_text += f"  上次总结: {last_summary.strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                status_text += f"  上次总结: 从未\n"
            status_text += "\n"
        
        if not self.message_cache:
            status_text += "暂无群组消息缓存\n"
        
        yield event.plain_result(status_text)
    
    @filter.command("qttest")
    async def test_command(self, event: AstrMessageEvent):
        """测试Telegram发送"""
        if not all([self.config['telegram_bot_token'], self.config['telegram_chat_id']]):
            yield event.plain_result("请先配置Telegram Bot Token和Chat ID")
            return
        
        test_message = f"🧪 测试消息\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n这是一条来自QQ群消息总结插件的测试消息。"
        
        try:
            await self.send_test_telegram(test_message)
            yield event.plain_result("测试消息已发送到Telegram")
        except Exception as e:
            yield event.plain_result(f"发送失败: {e}")
    
    async def send_test_telegram(self, message: str):
        """发送测试消息到Telegram"""
        url = f"https://api.telegram.org/bot{self.config['telegram_bot_token']}/sendMessage"
        
        data = {
            'chat_id': self.config['telegram_chat_id'],
            'text': message
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")

    async def terminate(self):
        """插件销毁方法"""
        logger.info("QQ群消息监听与AI总结Telegram推送插件已停止")
