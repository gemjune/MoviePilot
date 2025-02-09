from datetime import datetime
from typing import List, Optional, Tuple, Union

from ruamel.yaml import CommentedMap

from app.core.context import TorrentInfo
from app.log import logger
from app.modules import _ModuleBase
from app.modules.indexer.mtorrent import MTorrentSpider
from app.modules.indexer.spider import TorrentSpider
from app.modules.indexer.tnode import TNodeSpider
from app.modules.indexer.torrentleech import TorrentLeech
from app.schemas.types import MediaType
from app.utils.string import StringUtils


class IndexerModule(_ModuleBase):
    """
    索引模块
    """

    def init_module(self) -> None:
        pass

    def stop(self):
        pass

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        return "INDEXER", "builtin"

    def search_torrents(self, site: CommentedMap,
                        keywords: List[str] = None,
                        mtype: MediaType = None,
                        page: int = 0) -> List[TorrentInfo]:
        """
        搜索一个站点
        :param site:  站点
        :param keywords:  搜索关键词列表
        :param mtype:  媒体类型
        :param page:  页码
        :return: 资源列表
        """
        # 确认搜索的名字
        if not keywords:
            # 浏览种子页
            keywords = [None]

        # 开始索引
        result_array = []
        # 开始计时
        start_time = datetime.now()

        # 搜索多个关键字
        for search_word in keywords:
            # 可能为关键字或ttxxxx
            if search_word \
                    and site.get('language') == "en" \
                    and StringUtils.is_chinese(search_word):
                # 不支持中文
                logger.warn(f"{site.get('name')} 不支持中文搜索")
                continue

            # 去除搜索关键字中的特殊字符
            if search_word:
                search_word = StringUtils.clear(search_word, replace_word=" ", allow_space=True)

            try:
                if site.get('parser') == "TNodeSpider":
                    error_flag, result_array = TNodeSpider(site).search(
                        keyword=search_word,
                        page=page
                    )
                elif site.get('parser') == "TorrentLeech":
                    error_flag, result_array = TorrentLeech(site).search(
                        keyword=search_word,
                        page=page
                    )
                elif site.get('parser') == "mTorrent":
                    error_flag, result_array = MTorrentSpider(site).search(
                        keyword=search_word,
                        mtype=mtype,
                        page=page
                    )
                else:
                    error_flag, result_array = self.__spider_search(
                        search_word=search_word,
                        indexer=site,
                        mtype=mtype,
                        page=page
                    )
                # 有结果后停止
                if result_array:
                    break
            except Exception as err:
                logger.error(f"{site.get('name')} 搜索出错：{err}")

        # 索引花费的时间
        seconds = round((datetime.now() - start_time).seconds, 1)

        # 返回结果
        if not result_array or len(result_array) == 0:
            logger.warn(f"{site.get('name')} 未搜索到数据，耗时 {seconds} 秒")
            return []
        else:
            logger.info(f"{site.get('name')} 搜索完成，耗时 {seconds} 秒，返回数据：{len(result_array)}")
            # 合并站点信息，以TorrentInfo返回
            return [TorrentInfo(site=site.get("id"),
                                site_name=site.get("name"),
                                site_cookie=site.get("cookie"),
                                site_ua=site.get("ua"),
                                site_proxy=site.get("proxy"),
                                site_order=site.get("pri"),
                                **result) for result in result_array]

    @staticmethod
    def __spider_search(indexer: CommentedMap,
                        search_word: str = None,
                        mtype: MediaType = None,
                        page: int = 0) -> (bool, List[dict]):
        """
        根据关键字搜索单个站点
        :param: indexer: 站点配置
        :param: search_word: 关键字
        :param: page: 页码
        :param: mtype: 媒体类型
        :param: timeout: 超时时间
        :return: 是否发生错误, 种子列表
        """
        _spider = TorrentSpider(indexer=indexer,
                                mtype=mtype,
                                keyword=search_word,
                                page=page)

        return _spider.is_error, _spider.get_torrents()

    def refresh_torrents(self, site: CommentedMap) -> Optional[List[TorrentInfo]]:
        """
        获取站点最新一页的种子，多个站点需要多线程处理
        :param site:  站点
        :reutrn: 种子资源列表
        """
        return self.search_torrents(site=site)
