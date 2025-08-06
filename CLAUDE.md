# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个AstrBot QQ群消息监听与AI总结Telegram推送插件。该插件自动收集QQ群消息，使用AI生成总结，并将总结发送到Telegram频道。

## 核心架构

### 插件主体结构
- `main.py`: 插件主文件，包含`QQTelegramSummarizerPlugin`类
- `metadata.yaml`: 插件元数据配置
- `_conf_schema.json`: 插件配置模式定义
- `requirements.txt`: 依赖库列表

### 主要组件
- **消息监听器**: 使用`@filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)`监听QQ群消息
- **消息缓存**: 使用`collections.deque`缓存群消息，最多1000条
- **AI总结生成**: 支持内部LLM和外部API两种方式
- **Telegram推送**: 通过Telegram Bot API发送总结消息

## 配置系统

插件使用AstrBot的配置系统：
- 配置模式定义在`_conf_schema.json`中
- 支持消息阈值、时间窗口、Telegram设置、AI配置等
- 可通过WebUI插件管理页面修改配置

## 关键功能

### 消息收集与总结触发
- 监听指定QQ群（或所有群）的消息
- 当消息数量达到阈值且满足时间窗口条件时触发总结
- 支持防重复总结机制

### AI总结生成
- 内部LLM：使用AstrBot配置的LLM提供商
- 外部API：支持OpenAI兼容的API接口
- 可自定义总结提示词

### Telegram推送
- 格式化总结内容，包含时间、消息数量等信息
- 支持HTML格式的消息发送

## 开发指南

### 插件开发原则
- 继承`Star`基类并使用`@register`装饰器注册插件
- 所有处理函数必须写在插件类中
- 使用`from astrbot.api import logger`获取日志对象
- 错误处理：所有关键操作都包含try-catch块

### 消息处理模式
- 使用异步生成器：`yield event.plain_result(message)`
- 支持主动消息发送：`await event.send()`
- 消息链构建：使用`astrbot.api.message_components`

### 常用命令
- `/qtconfig`: 显示当前插件配置信息
- `/qtstatus`: 查看插件运行状态和缓存情况
- `/qttest`: 测试Telegram消息发送功能

## 依赖管理

- 主要依赖：`aiohttp>=3.8.0`
- AstrBot API依赖自动提供
- 使用requirements.txt管理第三方依赖

## 调试与测试

### 插件重载
- 在AstrBot WebUI的插件管理处找到插件
- 点击"管理" -> "重载插件"即可应用代码修改

### 日志输出
插件使用AstrBot的logger系统，日志级别包括：
- `logger.info()`: 常规信息
- `logger.warning()`: 警告信息  
- `logger.error()`: 错误信息

### 配置调试
- 插件启动时会输出配置类型和内容信息
- 支持配置对象兼容性处理

## 注意事项

- 插件类文件必须命名为`main.py`
- 配置文件中的敏感信息（如Token、API密钥）需要通过WebUI安全配置
- 异步操作使用aiohttp而非requests
- 所有网络请求都包含适当的错误处理