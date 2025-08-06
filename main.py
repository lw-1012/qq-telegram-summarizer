from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
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
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config  # 使用AstrBot的配置系统
        self.message_cache: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.last_summary_time: Dict[str, datetime] = {}

    async def initialize(self):
        """插件初始化"""
        logger.info("QQ群消息监听与AI总结Telegram推送插件初始化完成")
        if not all([self.config.get('telegram_bot_token'), self.config.get('telegram_chat_id')]):
            logger.warning("请在WebUI插件管理中配置Telegram相关参数")
        
        ai_config = self.config.get('ai_config', {})
        if not ai_config.get('use_internal_llm', True):
            if not ai_config.get('api_key'):
                logger.warning("请配置AI API密钥或启用内部LLM")
    
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """监听群消息"""
        try:
            # 安全地获取群组ID
            group_id = event.get_group_id()
            if not group_id:
                return  # 如果不是群消息，直接返回
            
            # 如果配置了特定群组，只监听这些群组
            target_groups = self.config.get('target_groups', [])
            if target_groups and group_id not in target_groups:
                return
            
            # 安全地获取用户名
            user_name = event.get_sender_name()
            if not user_name:
                user_name = "未知用户"
            
            message_str = event.message_str or ""
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
            message_threshold = self.config.get('message_threshold', 50)
            if len(messages) < message_threshold:
                return
            
            # 检查时间窗口
            now = datetime.now()
            last_summary = self.last_summary_time.get(group_id)
            time_window_hours = self.config.get('time_window_hours', 2)
            
            if last_summary and (now - last_summary).total_seconds() < time_window_hours * 3600:
                return
            
            # 筛选时间窗口内的消息
            cutoff_time = now - timedelta(hours=time_window_hours)
            recent_messages = []
            
            for msg in messages:
                msg_time = datetime.strptime(msg['time'], '%Y-%m-%d %H:%M:%S')
                if msg_time >= cutoff_time:
                    recent_messages.append(msg)
            
            if len(recent_messages) >= message_threshold:
                # 检查配置
                ai_config = self.config.get('ai_config', {})
                use_internal_llm = ai_config.get('use_internal_llm', True)
                
                if use_internal_llm:
                    provider = self.context.get_using_provider()
                    if not provider:
                        logger.warning("内部LLM提供商未配置，无法生成总结")
                        return
                else:
                    if not ai_config.get('api_key'):
                        logger.warning("外部AI API密钥未配置，无法生成总结")
                        return
                
                if not all([self.config.get('telegram_bot_token'), self.config.get('telegram_chat_id')]):
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
            message_threshold = self.config.get('message_threshold', 50)
            for msg in messages[-message_threshold:]:  # 取最新的N条消息
                formatted_messages.append(f"[{msg['time']}] {msg['user']}: {msg['message']}")
            
            messages_text = '\n'.join(formatted_messages)
            
            # 调用AI生成总结
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
            ai_config = self.config.get('ai_config', {})
            use_internal_llm = ai_config.get('use_internal_llm', True)
            summary_prompt = self.config.get('summary_prompt', '请总结以下QQ群聊天记录的主要话题和重点内容，用简洁的中文回复：\n\n{messages}')
            
            if use_internal_llm:
                # 使用内部LLM
                provider = self.context.get_using_provider()
                if not provider:
                    logger.error("内部LLM提供商未配置")
                    return None
                
                prompt = summary_prompt.format(messages=messages_text)
                llm_response = await provider.text_chat(
                    prompt=prompt,
                    session_id=None,
                    contexts=[],
                    image_urls=[],
                    system_prompt="你是一个专业的聊天记录总结助手。"
                )
                
                if llm_response.role == "assistant":
                    return llm_response.completion_text.strip()
                else:
                    logger.error(f"LLM返回异常角色: {llm_response.role}")
                    return None
            else:
                # 使用外部API
                return await self.get_external_ai_summary(messages_text, ai_config, summary_prompt)
                
        except Exception as e:
            logger.error(f"调用AI总结时出错: {e}")
            return None
    
    async def get_external_ai_summary(self, messages_text: str, ai_config: dict, summary_prompt: str) -> str:
        """调用外部AI API获取总结"""
        try:
            headers = {
                'Authorization': f'Bearer {ai_config.get("api_key", "")}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': ai_config.get('model', 'gpt-3.5-turbo'),
                'messages': [{
                    'role': 'user',
                    'content': summary_prompt.format(messages=messages_text)
                }],
                'max_tokens': 500,
                'temperature': 0.7
            }
            
            api_url = ai_config.get('api_url', 'https://api.openai.com/v1/chat/completions')
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content'].strip()
                    else:
                        logger.error(f"外部AI API请求失败: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"调用外部AI API时出错: {e}")
            return None
    
    async def send_to_telegram(self, group_id: str, summary: str, message_count: int):
        """发送消息到Telegram"""
        try:
            telegram_bot_token = self.config.get('telegram_bot_token', '')
            telegram_chat_id = self.config.get('telegram_chat_id', '')
            
            url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
            
            text = f"📊 QQ群 {group_id} 消息总结\n\n"
            text += f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            text += f"💬 消息数量: {message_count} 条\n\n"
            text += f"📝 AI总结:\n{summary}"
            
            data = {
                'chat_id': telegram_chat_id,
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
    async def config_info(self, event: AstrMessageEvent):
        """显示配置信息"""
        config_text = "📋 当前插件配置（请通过WebUI插件管理页面修改）:\n\n"
        config_text += f"📊 消息阈值: {self.config.get('message_threshold', 50)}\n"
        config_text += f"⏰ 时间窗口: {self.config.get('time_window_hours', 2)} 小时\n"
        
        ai_config = self.config.get('ai_config', {})
        config_text += f"🤖 使用内部LLM: {'是' if ai_config.get('use_internal_llm', True) else '否'}\n"
        
        if not ai_config.get('use_internal_llm', True):
            config_text += f"🔗 AI模型: {ai_config.get('model', 'gpt-3.5-turbo')}\n"
            config_text += f"🔑 外部API: {'已配置' if ai_config.get('api_key') else '未配置'}\n"
        
        config_text += f"📱 Telegram Token: {'已配置' if self.config.get('telegram_bot_token') else '未配置'}\n"
        config_text += f"💬 Telegram Chat ID: {'已配置' if self.config.get('telegram_chat_id') else '未配置'}\n"
        
        target_groups = self.config.get('target_groups', [])
        config_text += f"👥 监听群组: {target_groups if target_groups else '所有群组'}\n\n"
        config_text += "💡 提示: 请通过AstrBot WebUI的插件管理页面修改配置"
        
        yield event.plain_result(config_text)
    
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
        telegram_bot_token = self.config.get('telegram_bot_token', '')
        telegram_chat_id = self.config.get('telegram_chat_id', '')
        
        if not all([telegram_bot_token, telegram_chat_id]):
            yield event.plain_result("请先在WebUI插件管理中配置Telegram Bot Token和Chat ID")
            return
        
        test_message = f"🧪 测试消息\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n这是一条来自QQ群消息总结插件的测试消息。"
        
        try:
            await self.send_test_telegram(test_message)
            yield event.plain_result("测试消息已发送到Telegram")
        except Exception as e:
            yield event.plain_result(f"发送失败: {e}")
    
    async def send_test_telegram(self, message: str):
        """发送测试消息到Telegram"""
        telegram_bot_token = self.config.get('telegram_bot_token', '')
        telegram_chat_id = self.config.get('telegram_chat_id', '')
        
        url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        
        data = {
            'chat_id': telegram_chat_id,
            'text': message
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")

    async def terminate(self):
        """插件销毁方法"""
        logger.info("QQ群消息监听与AI总结Telegram推送插件已停止")
