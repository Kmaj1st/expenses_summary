"""
Author: Kmaj
"""

import asyncio
import random

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Type

from src.chat.message_receive.chat_stream import ChatStream
from src.common.data_models.database_data_model import DatabaseMessages
from src.common.logger import get_logger
from src.plugin_system.apis import send_api
from src.plugin_system.apis.config_api import get_global_config
from src.plugin_system.apis.llm_api import generate_with_model, \
    get_available_models
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    BaseCommand,
    BaseTool,
    ComponentInfo,
    ActionActivationType,
    ConfigField,
)
from src.webui.statistics_routes import DashboardData, StatisticsSummary, \
    get_dashboard_data

logger = get_logger("expenses_summary")


class ExpensesSummaryTool(BaseTool):
    """生成今日财务总结的工具"""

    name = "expenses_summary"
    description = "生成今日的财务总结的恶搞版string, 模仿户晨风的风格"
    available_for_llm = True

    async def execute(self) -> str:
        return get_summary_str(self)


class ExpensesSummaryAction(BaseAction):
    """生成今日财务总结的动作"""

    action_name = "expenses_summary_action"
    action_description = "生成今日财务总结动作"
    activation_type = ActionActivationType.ALWAYS  # 始终激活

    action_parameters = {}
    action_require = ["需要发送今日财务总结时",
                      "有人让你咬牙切齿时",
                      "有人让你模仿户晨风不可能不交时",
                      "有人让你公开收入时"]
    associated_types = ["text"]

    def __init__(
            self,
            action_data: dict,
            action_reasoning: str,
            cycle_timers: dict,
            thinking_id: str,
            chat_stream: ChatStream,
            plugin_config: Optional[dict] = None,
            action_message: Optional["DatabaseMessages"] = None,
            **kwargs,
    ):
        super().__init__(
            action_data,
            action_reasoning,
            cycle_timers,
            thinking_id,
            chat_stream,
            plugin_config,
            action_message,
            **kwargs
            )

        try:
            self.audio_enabled = self.get_config(
                key="audio.enabled",
                default=False
            )
            self.url = self.get_config(
                key="audio.file_location",
                default=(Path(__file__).parent / "audio.mp3").as_posix()
            )
        except Exception as e:
            logger.error(f"获取音频开启状态或音频路径出错,将不发送音频: {e}")
            self.audio_enabled = False

    async def execute(self) -> Tuple[bool, str]:
        """执行问候动作 - 这是核心功能"""
        # send summary
        try:
            summary_str = await get_summary_str(self)
            if not summary_str:
                return False, "未能生成财务总结, 总结为空"
            await self.send_text(summary_str)
        except Exception as e:
            logger.error(f"生成财务总结失败: {e}")
            return False, "生成财务总结时出错"

        stream_id = self.chat_stream.stream_id
        if self.audio_enabled:
            try:
                await send_api.custom_to_stream(
                    "voiceurl", self.url, stream_id)
            except Exception as e:
                logger.error(f"发送BGM音频失败: {e}")

        return True, "发送了财务总结"


class ExpensesSummaryCommand(BaseCommand):
    """生成财务总结Command - 响应/expenses命令"""

    command_name = "expenses_summary"
    command_description = "生成今日财务总结"

    command_pattern = r"^/expenses$"

    def __init__(self, message, plugin_config=None):
        super().__init__(message, plugin_config)
        try:
            self.audio_enabled = self.get_config(
                key="audio.enabled",
                default=False
            )
            self.url = self.get_config(
                key="audio.file_location",
                default=(Path(__file__).parent / "audio.mp3").as_posix()
            )
        except Exception as e:
            logger.error(f"获取音频开启状态或音频路径出错,将不发送音频: {e}")
            self.audio_enabled = False

    async def execute(self) -> Tuple[bool, str, bool]:
        try:
            summary_str = await get_summary_str(self)
            if not summary_str:
                return False, "未能生成财务总结, 总结为空", True
            await self.send_text(summary_str)
        except Exception as e:
            logger.error(f"生成财务总结失败: {e}")
            return False, "生成财务总结时出错", True

        stream_id = self.message.chat_stream.stream_id
        if self.audio_enabled:
            try:
                await send_api.custom_to_stream(
                    "voiceurl", self.url, stream_id)
            except Exception as e:
                logger.error(f"发送BGM音频失败: {e}")
        return True, "通过调用命令成功发送了财务总结", True


@register_plugin
class ExpensesSummaryPlugin(BasePlugin):
    """户晨风格式财务总结插件"""

    # 插件基本信息
    plugin_name: str = "expenses_summary_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名

    # 配置节描述
    config_section_descriptions = {"plugin": "插件基础信息",
                                   "fallback": "运行时出错的fallback配置",
                                   "audio": "音频发送信息(用于发送BGM)",
                                   "other": "其他"}

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "config_version": ConfigField(type=str, default="1.0.0",
                                          description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=True,
                                   description="是否启用插件"),
        },
        "fallback": {
            "xiao_name": ConfigField(
                type=list[str], default=["小爱"], description="出错时使用的小名列表"
            ),
            "location": ConfigField(
                type=list[str], default=["KFC", "卧室", "广州塔", "下水道"],
                description="出错时使用的位置列表"
            ),
            "poem": ConfigField(
                type=list[str],
                default=[
                    "How do you do, you like me and I like you.",
                    "Shut up! I read this inside the book I read before."
                ],
                description="出错时使用的诗句"
            )
        },
        "audio": {
            "enabled": ConfigField(type=bool, default=True,
                                   description="是否启用音频回复功能"),
            "file_location": ConfigField(
                type=str,
                default=(Path(__file__).parent / "audio.mp3").as_posix(),
                description="音频文件存储位置"
            ),
        },
        "other": {
            "thanks_list": ConfigField(type=List[str],
                                       default=["810", "艾斯比"],
                                       description="感谢名单")
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """
        获取插件组件
        """
        return [
            (ExpensesSummaryAction.get_action_info(), ExpensesSummaryAction),
            (ExpensesSummaryTool.get_tool_info(), ExpensesSummaryTool),
            (ExpensesSummaryCommand.get_command_info(), ExpensesSummaryCommand)
        ]


async def get_summary_str(
        caller: ExpensesSummaryAction
        | ExpensesSummaryCommand
        | ExpensesSummaryTool) -> str:
    """
    生成今日收入&支出总结
    """
    dash = await _get_dash_stats_today()

    model_expenses_str = _get_model_expenses_str(dash=dash)

    today = datetime.now().strftime("%Y年%m月%d日")

    config_values = await _get_config_values(caller=caller)
    personality, names, fb_xnames, fb_loc, fb_poems = config_values

    xiao_name, location, went_to, poem = await _get_settings(
        personality=personality,
        names=names,
        fb_xnames=fb_xnames,
        fb_loc=fb_loc,
        fb_poems=fb_poems
    )

    ss: StatisticsSummary = dash.summary

    try:
        thanks_list = caller.get_config(
            key="other.thanks_list",
            default=["810", "艾斯比"]
        )
        thanks_str = "、".join(thanks_list)
    except Exception as e:
        logger.error(f"获取感谢名单失败: {e}")
        thanks_str = "了不起的比尔·盖茨、马斯克·扎克伯格"

    # summary str
    summary = f"我是{xiao_name}，我在{location}向各位网友兼股东汇报{today}我在全网的收入情况。\n"
    summary += f"{today}收入再次创出历史新高📈✨\n"
    summary += f"我在{today}的税前总收入为：0万0元💸。其中：所有收入 0万0元。\n"
    summary += "除广告收入和带货佣金外，在缴纳了约25%即 0万0元 的个人所得税之后，"
    summary += "此为系统自动扣除，"
    summary += "***不🙅‍♀️可🙅‍♀️能🙅‍♀️不🙅‍♀️交*** 😡💢（咬牙切齿🦷），"
    summary += "我的税后总收入为 0万0元🙃。\n\n"

    summary += "以上为我的收入情况，下面是我的支出情况👇\n\n"

    summary += f"{today}{went_to}\n"
    summary += f"累计请求API {ss.total_requests} 次🔁，"
    summary += f"回复消息{ss.total_replies}条✉️。\n"
    summary += f"我的回复成本累计为：{ss.total_cost:.4f} 元💔💰。其中：\n"
    summary += model_expenses_str

    summary += f"所以，{today}我的净收入为 -{ss.total_cost:.4f} 元 📉😵💫。\n\n"

    summary += f"{xiao_name}一路走来，是因为屏幕前各位群友的支持🤝💛才有了不一样的人生🌟。\n"
    summary += f"{poem} 📜✨\n"
    summary += "也正是你们的陪伴，给了我笃定前行的勇气💪🕊️。\n"
    summary += f"再次感谢各位群友的支持🙏尤其要感谢 {thanks_str} 两位的强力支持⚡🔥！\n"
    summary += "以及所有群员的陪伴❤️ 再次谢谢大家🙇‍♂️🙇‍♀️！"

    return summary


def _get_model_expenses_str(dash: DashboardData) -> str:
    """
    获取模型费用字符串

    Args:
        dash: DashboardData

    Returns:
        str: 模型费用字符串
    """
    s = ""
    for m in dash.model_stats:
        s += f"{m.model_name}：{m.total_cost:.4f} 元\n"
    s += "\n"
    return s


async def _get_settings(personality: str,
                        names: List[str],
                        fb_xnames: List[str],
                        fb_loc: List[str],
                        fb_poems: List[str]) -> Tuple[str, str, str]:
    """
    获取财报中的小名，地点和诗句

    Args:
        personality: 人格
        names: 设定的名字
        fb_xnames: fallback的名字
        fb_loc: fallback的地点
        fb_poems: fallback的诗

    Returns:
        Tuple[str, str, str]: 小名，地点和诗句
    """
    xiao_name = None
    location = None
    went_to = None
    poem = None

    try:
        replyer = get_available_models()["replyer"]
        # generate xiao_name, location and poem concurrently
        xiao_name_task = generate_with_model(
            prompt="从以下名字中任选一个构造可爱小名,只返回“小X”形式."
            f"不要任何解释:{','.join(names)}",
            model_config=replyer,
            temperature=0.5,
            max_tokens=8
        )
        location_task = generate_with_model(
            prompt=f"她{personality},她现在最不可能在什么地方?"
            "可以是真实城市,自宅卧室,火星,深海,丛林,KFC,任意梦幻或搞笑地点."
            "尽量搞怪.只返回地点名称,可以很长也可以很短.",
            model_config=replyer,
            temperature=0.5,
            max_tokens=60
        )
        went_to_task = generate_with_model(
            prompt="她{personality},她现在最不可能在什么地方?"
            "按照这个模板回复:"
            "\"我去了：{{地点}}、{{地点}}、{{地点}}、{{地点}} 回复群员信息📱。\""
            "请把所有的{{地点}}都替换为那些地方."
            "所有的地点后面要加一个emoji."
            "可以是真实城市,自宅卧室,火星,深海,丛林,KFC,任意梦幻或搞笑地点."
            "尽量搞怪.只返回那句套了模板的句子,可以很长也可以很短.",
            model_config=replyer,
            temperature=0.5,
            max_tokens=120
        )
        poem_task = generate_with_model(
            prompt="给我两句诗句(可以是中文,古诗改编,日文,英文,任何语言都行)."
            "控制在40字以内.只返回诗句.",
            model_config=replyer,
            temperature=0.5,
            max_tokens=60
        )

        raw_results = await asyncio.gather(
            xiao_name_task,
            location_task,
            went_to_task,
            poem_task,
            return_exceptions=True
        )

        def safe_extract(task_result):
            if isinstance(task_result, Exception):
                return ""
            success, result, _, _ = task_result
            return (result or "").strip().replace("\n", " ") if success else ""

        xiao_name, location, went_to, poem = [
            safe_extract(r) for r in raw_results]
    except Exception as e:
        logger.error(f"生成随机要素失败, 将使用fallback: {e}")
    try:
        if not xiao_name:
            xiao_name = random.choice(fb_xnames)
        if not location:
            location = random.choice(fb_loc)
        if not went_to:
            went_to = random.choice(fb_loc)
        if not poem:
            poem = random.choice(fb_poems)
    except Exception as e:
        raise Exception(f"获取fallback随机要素失败: {e}")

    return xiao_name, location, went_to, poem


async def _get_config_values(caller: ExpensesSummaryAction
                             | ExpensesSummaryCommand
                             | ExpensesSummaryTool) -> tuple[
        str, List[str], List[str], List[str], List[str]]:
    """
    获取插件配置

    Args:
        caller: ExpensesSummaryAction
            | ExpensesSummaryCommand
            | ExpensesSummaryTool

    Returns:
        str: 人格
        List[str]: 设定的名字
        List[str]: fallback的名字
        List[str]: fallback的地点
        List[str]: fallback的诗
    """
    # read config
    try:
        nickname = get_global_config("bot.nickname", "我")
        alias_names = get_global_config("bot.alias_names", [])
        personality = get_global_config("personality.personality", "")

        names = [nickname] + alias_names

        # fallback values
        fb_xnames = caller.get_config(
            key="fallback.xiao_name",
            default=["小爱"]
        )
        fb_loc = caller.get_config(
            key="fallback.location",
            default=["KFC", "卧室", "广州塔", "下水道"]
        )
        fb_poems = caller.get_config(
            key="fallback.poem",
            default=[
                "How do you do, you like me and I like you.",
                "Shut up! I read this inside the book I read before."
            ]
        )
    except Exception as e:
        logger.error(f"读取配置失败,使用默认值: {e}")
        names = ["小爱"]
        fb_loc = ["KFC", "卧室", "广州塔", "下水道"]
        fb_poems = [
            "How do you do, you like me and I like you.",
            "Shut up! I read this inside the book I read before."
        ]

    return personality, names, fb_xnames, fb_loc, fb_poems


async def _get_dash_stats_today() -> DashboardData:
    """
    获取今日(从0点到现在的)仪表盘数据

    Returns:
        DashboardData: 今日仪表盘数据
    """
    try:
        return await get_dashboard_data(hours=_hours_from_now())
    except Exception as e:
        logger.error(f"获取仪表盘数据失败: {e}")
        return DashboardData()


def _hours_from_now() -> datetime:
    """
    获取从0点到现在的小时数

    Returns:
        int: 从0点到现在的小时数
    """
    now = datetime.now()
    today_zero = now.replace(hour=0,
                             minute=0,
                             second=0,
                             microsecond=0)
    delta_hours = int((now - today_zero).total_seconds() // 3600)
    return delta_hours
