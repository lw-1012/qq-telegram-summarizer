Context
暴露给插件的上下文, 该类的作用就是为插件提供接口和数据。

属性:
provider_manager: 供应商管理器对象
platform_manager: 平台管理器对象
方法:
插件相关
get_registered_star

get_registered_star(star_name: str) -> StarMetadata
该方法根据输入的插件名获取插件的元数据对象, 该对象包含了插件的基本信息, 例如插件的名称、版本、作者等。 该方法可以获取其他插件的元数据。 StarMetadata 详情见StarMetadata

get_all_stars

get_all_stars() -> List[StarMetadata]
该方法获取所有已注册的插件的元数据对象列表, 该列表包含了所有插件的基本信息。 StarMetadata 详情见StarMetadata

函数工具相关
get_llm_tool_manager

get_llm_tool_manager() -> FuncCall
该方法获取 FuncCall 对象, 该对象用于管理注册的所有函数调用工具。

activate_llm_tool

activate_llm_tool(name: str) -> bool
该方法用于激活指定名称的已经注册的函数调用工具, 已注册的函数调用工具默认为激活状态, 不需要手动激活。 如果没能找到指定的函数调用工具, 则返回False。

deactivate_llm_tool

deactivate_llm_tool(name: str) -> bool
该方法用于停用指定名称的已经注册的函数调用工具。 如果没能找到指定的函数调用工具, 则返回False。

供应商相关
register_provider

register_provider(provider: Provider)
该方法用于注册一个新用于文本生成的的供应商对象, 该对象必须是 Provider 类。 用于文本生成的的 Provider 类型为 Chat_Completion, 后面将不再重复。

get_provider_by_id

get_provider_by_id(provider_id: str) -> Provider
该方法根据输入的供应商 ID 获取供应商对象。

get_all_providers

get_all_providers() -> List[Provider]
该方法获取所有已注册的用于文本生成的供应商对象列表。

get_all_tts_providers

get_all_tts_providers() -> List[TTSProvider]
该方法获取所有已注册的文本到语音供应商对象列表。

get_all_stt_providers

get_all_stt_providers() -> List[STTProvider]
该方法获取所有已注册的语音到文本供应商对象列表。

get_using_provider

get_using_provider() -> Provider
该方法获取当前使用的用于文本生成的供应商对象。

get_using_tts_provider

get_using_tts_provider() -> TTSProvider
该方法获取当前使用的文本到语音供应商对象。

get_using_stt_provider

get_using_stt_provider() -> STTProvider
该方法获取当前使用的语音到文本供应商对象。

其他
get_config

get_config() -> AstrBotConfig
该方法获取当前 AstrBot 的配置对象, 该对象包含了插件的所有配置项与 AstrBot Core 的所有配置项(谨慎修改!)。

get_db

get_db() -> BaseDatabase
该方法获取 AstrBot 的数据库对象, 该对象用于访问数据库, 该对象是 BaseDatabase 类的实例。

get_event_queue

get_event_queue() -> Queue
该方法用于获取 AstrBot 的事件队列, 这是一个异步队列, 其中的每一项都是一个 AstrMessageEvent 对象。

get_platform

get_platform(platform_type: Union[PlatformAdapterType, str]) -> Platform
该方法用于获取指定类型的平台适配器对象。

send_message

send_message(session: Union[str, MessageSesion], message_chain: MessageChain) -> bool
该方法可以根据会话的唯一标识符-session(unified_msg_origin)主动发送消息。

它接受两个参数：

session: 会话的唯一标识符, 可以是字符串或 MessageSesion 对象， 获取该标识符参考：[获取会话的 session]。
message_chain: 消息链对象, 该对象包含了要发送的消息内容, 该对象是 MessageChain 类的实例。
该方法返回一个布尔值, 表示是否找到对应的消息平台。

注意: 该方法不支持 qq_official 平台!!