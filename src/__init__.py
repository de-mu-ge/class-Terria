"""序章工程包。

结构：
    core/    引擎无关层（循环、场景栈、状态机、资源、时间线）
    render/  渲染抽象 + pygame 实现
    ui/      对话框、名字条、菜单、字幕、过场遮罩
    scenes/  每个 Scene 一个类 / 数据驱动演出
    data/    数据读取（内容在项目根 data/*.json）
    assets/  资源路径解析（只读）
"""

__version__ = "0.1.0"
