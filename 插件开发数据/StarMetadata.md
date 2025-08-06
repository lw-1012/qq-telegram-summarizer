StarMetadata
插件的元数据。

属性:
基础属性
name(str): 插件名称
author(str): 插件作者
desc(str): 插件简介
version(str): 插件版本
repo(str): 插件仓库地址
插件类, 模块属性
star_cls_type(type): 插件类对象类型, 例如你的插件类名为HelloWorld, 该属性就是<type 'HelloWorld'>
star_cls(object): 插件的类对象, 它是一个实例, 你可以使用它调用插件的方法和属性
module_path(str): 插件模块的路径
module(ModuleType): 插件的模块对象
root_dir_name(str): 插件的目录名称
插件身份&状态属性
reserved(bool): 是否为 AstrBot 保留插件
activated(bool): 是否被激活
插件配置
config(AstrBotConfig): 插件配置对象
注册的 Handler 全名列表
star_handler_full_names(List(str)): 注册的 Handler 全名列表, Handler 相关请见核心代码解释->插件注册(施工中)
其它
该类实现了__str__方法, 因此你可以打印插件信息。