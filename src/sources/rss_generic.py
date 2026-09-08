"""通用 RSS 数据源适配器 - 支持任意 RSS/Atom Feed（AI 博客等）"""

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

from src.models import RawItem, SourceType
from src.sources.base import BaseSource

logger = logging.getLogger(__name__)

USER_AGENT = "AI-News-Agent/1.0 (RSS Reader)"

# ============================================================
# AI 与机器人相关 RSS 源（国内外）
# ============================================================
AI_BLOG_FEEDS = {
    # ===================== 一、国外 AI 官方博客 =====================
    "openai_blog": "https://openai.com/blog/rss.xml",
    "deepmind_blog": "https://deepmind.google/blog/rss.xml",
    "anthropic_blog": "https://www.anthropic.com/blog/rss.xml",
    "google_ai_blog": "https://ai.googleblog.com/feeds/posts/default",
    "meta_ai_blog": "https://ai.meta.com/blog/feed/",
    "microsoft_ai_blog": "https://www.microsoft.com/en-us/research/blog/category/ai/feed/",
    "huggingface_blog": "https://huggingface.co/blog/feed.xml",
    "pytorch_blog": "https://pytorch.org/blog/feed.xml",
    "ollama_blog": "https://ollama.com/blog/rss",

    # ===================== 二、国外机器人官方博客/新闻 =====================
    "nvidia_robotics": "https://blogs.nvidia.com/blog/tag/robotics/feed/",
    "boston_dynamics": "https://bostondynamics.com/feed/",           # 需确认
    "universal_robots": "https://www.universal-robots.com/feed/",    # 需确认
    "clearpath_robotics": "https://clearpathrobotics.com/feed/",     # 需确认
    "robotiq": "https://blog.robotiq.com/feed",
    "kuka_news": "https://www.kuka.com/en-us/company/news/feed",     # 需确认
    "flexiv_news": "https://www.flexiv.com/feed/",                   # 需确认
    "atomrobot_news": "https://www.atomrobot.com/feed/",             # 需确认
    "aethon_news": "https://aethon.com/feed/",                       # 需确认
    "figure_ai": "https://www.figure.ai/feed/",                      # 需确认
    "agility_robotics": "https://agilityrobotics.com/feed/",         # 需确认
    "1x_tech": "https://www.1x.tech/feed/",                          # 需确认
    "covariant": "https://covariant.ai/feed/",                       # 需确认

    # ===================== 三、arXiv 学术论文（AI/机器人） =====================
    "arxiv_ai": "http://export.arxiv.org/rss/cs.AI",
    "arxiv_robotics": "http://export.arxiv.org/rss/cs.RO",
    "arxiv_ml": "http://export.arxiv.org/rss/cs.LG",
    "arxiv_cv": "http://export.arxiv.org/rss/cs.CV",

    # ===================== 四、国外科技媒体 AI/机器人频道 =====================
    "techcrunch_ai": "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "venturebeat_ai": "https://venturebeat.com/category/ai/feed/",
    "theverge_ai": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "mit_tech_review_ai": "https://www.technologyreview.com/feed/ai/",
    "ieee_spectrum_robotics": "https://spectrum.ieee.org/feeds/topic/robotics.rss",

    # ===================== 五、国外机器人行业媒体 =====================
    "the_robot_report": "https://www.therobotreport.com/feed/",
    "robohub": "https://robohub.org/feed/",
    "robotics_business_review": "https://www.roboticsbusinessreview.com/feed/",
    "new_atlas_robotics": "https://newatlas.com/robotics/index.rss",
    "techxplore_robotics": "https://techxplore.com/rss-feed/robotics-news/",
    "mit_news_robotics": "https://news.mit.edu/topic/mitrobotics-rss.xml",
    "science_daily_robotics": "https://www.sciencedaily.com/rss/matter_energy/robotics.xml",
    "azorobotics": "https://www.azorobotics.com/syndication.axd",
    "unite_ai_robotics": "https://www.unite.ai/feed/",
    "singularity_hub_robotics": "https://singularityhub.com/tag/robotics/feed/",
    "weekly_robotics": "http://weeklyrobotics.com/atom.xml",

    # ===================== 六、国内 AI 垂直媒体 =====================
    "jiqizhixin": "https://www.jiqizhixin.com/rss",
    "qbitai": "https://www.qbitai.com/feed",
    "leiphone_ai": "https://www.leiphone.com/category/ai/feed",

    # ===================== 七、国内机器人公司官方新闻 =====================
    "unitree": "https://www.unitree.com/feed/",                      # 宇树科技（需确认）
    "ubtech": "https://www.ubtrobot.com/feed/",                      # 优必选（需确认）
    "agibot": "https://www.agibot.com/feed/",                        # 智元机器人（需确认）
    "mechmind": "https://www.mech-mind.com/feed/",                   # 梅卡曼德（需确认）
    "agilex": "https://www.agilex.ai/feed/",                         # 松灵机器人（需确认）
    "flexiv_cn": "https://www.flexiv.com.cn/feed/",                  # 非夕科技（需确认）
    "atomrobot_cn": "https://www.atomrobot.com/feed/",               # 阿童木机器人（需确认）
    "bangbang_robot": "https://www.bangbangrobot.com/feed/",         # 邦邦机器人（需确认）
    "agile_robots": "https://www.agile-robots.com/feed/",            # 思灵机器人（需确认）

    # ============================================================
    # 注意：以下源可能混入泛科技内容，默认注释，如需启用请自行测试
    # ============================================================
    # "36kr_ai": "https://36kr.com/feed",           # 36氪（全站，非 AI 专属）
    # "tmtpost_ai": "https://www.tmtpost.com/feed", # 钛媒体（全站，非 AI 专属）
}


class GenericRSSSource(BaseSource):
    """通用 RSS 数据源，可对接任意 RSS/Atom Feed"""

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    @property
    def source_id(self) -> str:
        return f"rss:{self.name}"

    @property
    def default_interval(self) -> int:
        return 3600  # 1 hour

    async def fetch(self, since: datetime | None = None) -> list[RawItem]:
        logger.info(f"Fetching RSS [{self.name}] ...")
        try:
            async with httpx.AsyncClient(
                timeout=30,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(self.url)
                resp.raise_for_status()
            feed = feedparser.parse(resp.text)
        except Exception as e:
            logger.error(f"Fetch [{self.name}] failed: {e}")
            return []

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS [{self.name}] parse error: {feed.bozo_exception}")
            return []

        items: list[RawItem] = []
        for entry in feed.entries:
            published = self._parse_time(entry)
            if since and published and published <= since:
                continue

            content = ""
            if entry.get("content"):
                content = entry["content"][0].get("value", "")
            elif entry.get("summary"):
                content = entry["summary"]
            elif entry.get("description"):
                content = entry["description"]

            item = RawItem(
                source_type=SourceType.RSS,
                source_id=entry.get("id", entry.get("link", "")),
                title=entry.get("title", ""),
                content=content,
                url=entry.get("link", ""),
                author=entry.get("author", ""),
                published_at=published,
                metadata={
                    "feed_name": self.name,
                    "feed_url": self.url,
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                },
            )
            items.append(item)

        # ---------- AI 过滤（LLM 判断是否相关） ----------
        if items:
            try:
                from src.tools.ai_filter import batch_filter_ai
                titles = [item.title for item in items]
                descs = [item.content[:80] for item in items]
                ai_indices = await batch_filter_ai(titles, descs)
                items = [items[i] for i in range(len(items)) if i in ai_indices]
                logger.info(f"RSS [{self.name}]: AI filtered {len(ai_indices)}/{len(titles)} items")
            except Exception as e:
                logger.warning(f"RSS [{self.name}] AI filter failed: {e}")

        logger.info(f"RSS [{self.name}]: fetched {len(items)} items")
        return items

    @staticmethod
    def _parse_time(entry) -> datetime | None:
        for field in ("published_parsed", "updated_parsed"):
            parsed = entry.get(field)
            if parsed:
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
        return None


def get_ai_blog_sources() -> list[GenericRSSSource]:
    """获取预置的 AI 博客 RSS 源列表"""
    return [GenericRSSSource(name, url) for name, url in AI_BLOG_FEEDS.items()]
