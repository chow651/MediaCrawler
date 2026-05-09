# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/core.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import os
import random
from asyncio import Task
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import douyin as douyin_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from tools.adaptive_delay import AdaptiveDelay
from tools.checkpoint import CheckpointManager
from tools.captcha_handler import CaptchaHandler, CaptchaStrategy
from var import crawler_type_var, source_keyword_var

from .client import DouYinClient
from .exception import DataFetchError
from .field import PublishTimeType
from .help import parse_video_info_from_url, parse_creator_info_from_url
from .login import DouYinLogin


class DouYinCrawler(AbstractCrawler):
    context_page: Page
    dy_client: DouYinClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self) -> None:
        self.index_url = "https://www.douyin.com"
        self.cookie_urls = [
            "https://douyin.com",
            self.index_url,
            "https://creator.douyin.com",
            "https://douhot.douyin.com",
            "https://live.douyin.com",
        ]
        self.cdp_manager = None
        self.ip_proxy_pool = None  # Proxy IP pool for automatic proxy refresh
        
        # 初始化增强模块
        self.delay_controller = None
        self.checkpoint_manager = None
        self.captcha_handler = None

    async def start(self) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # Select startup mode based on configuration
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[DouYinCrawler] 使用CDP模式启动浏览器")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    None,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[DouYinCrawler] 使用标准模式启动浏览器")
                # Launch a browser context.
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    user_agent=None,
                    headless=config.HEADLESS,
                )
                # stealth.min.js is a js script to prevent the website from detecting the crawler.
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)
            
            # 初始化验证码处理器
            if config.ENABLE_CAPTCHA_DETECTION:
                strategy = CaptchaStrategy(config.CAPTCHA_STRATEGY)
                self.captcha_handler = CaptchaHandler(
                    page=self.context_page,
                    strategy=strategy,
                    max_wait_time=config.CAPTCHA_MAX_WAIT_TIME,
                    max_retries=config.CAPTCHA_MAX_RETRIES,
                )
                utils.logger.info(f"[DouYinCrawler] 验证码检测已启用，策略: {strategy.value}")

            self.dy_client = await self.create_douyin_client(httpx_proxy_format)
            if not await self.dy_client.pong(browser_context=self.browser_context):
                login_obj = DouYinLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",  # you phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.dy_client.update_cookies(
                    browser_context=self.browser_context,
                    urls=self.cookie_urls,
                )
            
            # 检查登录后的验证码
            if self.captcha_handler:
                can_continue = await self.captcha_handler.handle_captcha()
                if not can_continue:
                    utils.logger.error("[DouYinCrawler] 登录后验证码处理失败，终止")
                    return
            
            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                # Search for notes and retrieve their comment information.
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                # Get the information and comments of the specified post
                await self.get_specified_awemes()
            elif config.CRAWLER_TYPE == "creator":
                # Get the information and comments of the specified creator
                await self.get_creators_and_videos()

            # 保存断点并输出统计
            if self.checkpoint_manager:
                self.checkpoint_manager.save_and_close()
                stats = self.checkpoint_manager.get_stats()
                utils.logger.info(f"[DouYinCrawler] 断点统计: {stats}")
            
            if self.delay_controller:
                stats = self.delay_controller.get_stats()
                utils.logger.info(f"[DouYinCrawler] 延迟统计: {stats}")
            
            if self.captcha_handler:
                stats = self.captcha_handler.get_stats()
                utils.logger.info(f"[DouYinCrawler] 验证码统计: {stats}")

            utils.logger.info("[DouYinCrawler.start] Douyin Crawler finished ...")

    async def search(self) -> None:
        utils.logger.info("[DouYinCrawler.search] Begin search douyin keywords")
        dy_limit_count = 10  # douyin limit page fixed value
        if config.CRAWLER_MAX_NOTES_COUNT < dy_limit_count:
            config.CRAWLER_MAX_NOTES_COUNT = dy_limit_count
        start_page = config.START_PAGE  # start page number
        
        # 初始化断点管理器
        if config.ENABLE_CHECKPOINT:
            self.checkpoint_manager = CheckpointManager(
                platform="dy",
                crawler_type="search",
                checkpoint_dir=config.CHECKPOINT_DIR,
                save_interval=config.CHECKPOINT_SAVE_INTERVAL,
            )
        
        # 初始化延迟控制器
        if config.ENABLE_ADAPTIVE_DELAY:
            self.delay_controller = AdaptiveDelay(
                base_delay=config.ADAPTIVE_BASE_DELAY,
                min_delay=config.ADAPTIVE_MIN_DELAY,
                max_delay=config.ADAPTIVE_MAX_DELAY,
                backoff_factor=config.ADAPTIVE_BACKOFF_FACTOR,
                recovery_factor=config.ADAPTIVE_RECOVERY_FACTOR,
                success_threshold=config.ADAPTIVE_SUCCESS_THRESHOLD,
            )
        
        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(f"[DouYinCrawler.search] Current keyword: {keyword}")
            aweme_list: List[str] = []
            page = 0
            dy_search_id = ""
            while (page - start_page + 1) * dy_limit_count <= config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[DouYinCrawler.search] Skip {page}")
                    page += 1
                    continue
                try:
                    utils.logger.info(f"[DouYinCrawler.search] search douyin keyword: {keyword}, page: {page}")
                    
                    # 自适应延迟
                    if self.delay_controller:
                        await self.delay_controller.wait()
                    
                    posts_res = await self.dy_client.search_info_by_keyword(
                        keyword=keyword,
                        offset=page * dy_limit_count - dy_limit_count,
                        publish_time=PublishTimeType(config.PUBLISH_TIME_TYPE),
                        search_id=dy_search_id,
                    )
                    
                    # 检查验证码
                    if self.captcha_handler:
                        can_continue = await self.captcha_handler.handle_captcha()
                        if not can_continue:
                            utils.logger.warning("[DouYinCrawler.search] 验证码处理失败，跳过当前批次")
                            break
                    
                    # 请求成功，更新延迟控制器
                    if self.delay_controller:
                        self.delay_controller.on_success()
                    
                except Exception as e:
                    utils.logger.error(f"[DouYinCrawler.search] Error: {e}")
                    
                    # 请求失败，更新延迟控制器
                    if self.delay_controller:
                        self.delay_controller.on_error()
                    
                    # 检查是否是验证码导致的错误
                    if self.captcha_handler:
                        can_continue = await self.captcha_handler.handle_captcha()
                        if not can_continue:
                            break
                    
                    page += 1
                    continue
                
                page += 1
                dy_search_id = posts_res.get("log_pb", {}).get("impr_id", "")
                
                utils.logger.info(
                    f"[DouYinCrawler.search] Keyword: {keyword}, "
                    f"Page: {page}, Got {len(aweme_list)} posts"
                )
            
            utils.logger.info(
                f"[DouYinCrawler.search] Finished keyword: {keyword}, "
                f"Total: {len(aweme_list)} posts"
            )

    async def get_specified_awemes(self) -> None:
        """Get the information and comments of the specified post"""
        utils.logger.info("[DouYinCrawler.get_specified_awemes] Begin")
        
        # 初始化断点管理器
        if config.ENABLE_CHECKPOINT:
            self.checkpoint_manager = CheckpointManager(
                platform="dy",
                crawler_type="detail",
                checkpoint_dir=config.CHECKPOINT_DIR,
                save_interval=config.CHECKPOINT_SAVE_INTERVAL,
            )
        
        # 初始化延迟控制器
        if config.ENABLE_ADAPTIVE_DELAY:
            self.delay_controller = AdaptiveDelay(
                base_delay=config.ADAPTIVE_BASE_DELAY,
                min_delay=config.ADAPTIVE_MIN_DELAY,
                max_delay=config.ADAPTIVE_MAX_DELAY,
                backoff_factor=config.ADAPTIVE_BACKOFF_FACTOR,
                recovery_factor=config.ADAPTIVE_RECOVERY_FACTOR,
                success_threshold=config.ADAPTIVE_SUCCESS_THRESHOLD,
            )
        
        for aweme_url in config.DY_SPECIFIED_ID_LIST:
            aweme_id = parse_video_info_from_url(aweme_url)
            if not aweme_id:
                utils.logger.warning(f"[DouYinCrawler.get_specified_awemes] Invalid URL: {aweme_url}")
                continue
            
            # 断点检查
            if self.checkpoint_manager and self.checkpoint_manager.is_processed(aweme_id):
                utils.logger.info(f"[DouYinCrawler.get_specified_awemes] Skip processed: {aweme_id}")
                continue
            
            try:
                # 自适应延迟
                if self.delay_controller:
                    await self.delay_controller.wait()
                
                aweme_info = await self.dy_client.get_aweme_detail(aweme_id)
                
                # 请求成功，更新延迟控制器
                if self.delay_controller:
                    self.delay_controller.on_success()
                
                # 检查验证码
                if self.captcha_handler:
                    can_continue = await self.captcha_handler.handle_captcha()
                    if not can_continue:
                        break
                
                if aweme_info:
                    await douyin_store.save_aweme(aweme_info)
                    
                    # 标记为已处理
                    if self.checkpoint_manager:
                        self.checkpoint_manager.mark_processed(aweme_id)
                    
                    # 获取评论
                    if config.ENABLE_GET_COMMENTS:
                        comments = await self.dy_client.get_aweme_comments(aweme_id)
                        for comment in comments:
                            await douyin_store.save_comment(aweme_id, comment)
                
            except Exception as e:
                utils.logger.error(f"[DouYinCrawler.get_specified_awemes] Error for {aweme_id}: {e}")
                
                # 请求失败，更新延迟控制器
                if self.delay_controller:
                    self.delay_controller.on_error()
                
                # 检查是否是验证码导致的错误
                if self.captcha_handler:
                    can_continue = await self.captcha_handler.handle_captcha()
                    if not can_continue:
                        break
        
        utils.logger.info("[DouYinCrawler.get_specified_awemes] Finished")

    async def get_creators_and_videos(self) -> None:
        """Get the information and comments of the specified creator"""
        utils.logger.info("[DouYinCrawler.get_creators_and_videos] Begin")
        
        # 初始化断点管理器
        if config.ENABLE_CHECKPOINT:
            self.checkpoint_manager = CheckpointManager(
                platform="dy",
                crawler_type="creator",
                checkpoint_dir=config.CHECKPOINT_DIR,
                save_interval=config.CHECKPOINT_SAVE_INTERVAL,
            )
        
        # 初始化延迟控制器
        if config.ENABLE_ADAPTIVE_DELAY:
            self.delay_controller = AdaptiveDelay(
                base_delay=config.ADAPTIVE_BASE_DELAY,
                min_delay=config.ADAPTIVE_MIN_DELAY,
                max_delay=config.ADAPTIVE_MAX_DELAY,
                backoff_factor=config.ADAPTIVE_BACKOFF_FACTOR,
                recovery_factor=config.ADAPTIVE_RECOVERY_FACTOR,
                success_threshold=config.ADAPTIVE_SUCCESS_THRESHOLD,
            )
        
        for creator_url in config.DY_CREATOR_ID_LIST:
            sec_user_id = parse_creator_info_from_url(creator_url)
            if not sec_user_id:
                utils.logger.warning(f"[DouYinCrawler.get_creators_and_videos] Invalid URL: {creator_url}")
                continue
            
            # 断点检查
            if self.checkpoint_manager and self.checkpoint_manager.is_processed(sec_user_id):
                utils.logger.info(f"[DouYinCrawler.get_creators_and_videos] Skip processed: {sec_user_id}")
                continue
            
            try:
                # 自适应延迟
                if self.delay_controller:
                    await self.delay_controller.wait()
                
                # 获取创作者信息
                creator_info = await self.dy_client.get_creator_info(sec_user_id)
                
                # 请求成功，更新延迟控制器
                if self.delay_controller:
                    self.delay_controller.on_success()
                
                # 检查验证码
                if self.captcha_handler:
                    can_continue = await self.captcha_handler.handle_captcha()
                    if not can_continue:
                        break
                
                if creator_info:
                    await douyin_store.save_creator(creator_info)
                    
                    # 获取创作者的视频列表
                    aweme_list = await self.dy_client.get_creator_videos(sec_user_id)
                    
                    for aweme_info in aweme_list:
                        aweme_id = aweme_info.get("aweme_id")
                        
                        # 断点检查
                        if self.checkpoint_manager and self.checkpoint_manager.is_processed(aweme_id):
                            continue
                        
                        await douyin_store.save_aweme(aweme_info)
                        
                        # 标记为已处理
                        if self.checkpoint_manager:
                            self.checkpoint_manager.mark_processed(aweme_id)
                        
                        # 获取评论
                        if config.ENABLE_GET_COMMENTS:
                            comments = await self.dy_client.get_aweme_comments(aweme_id)
                            for comment in comments:
                                await douyin_store.save_comment(aweme_id, comment)
                    
                    # 标记创作者为已处理
                    if self.checkpoint_manager:
                        self.checkpoint_manager.mark_processed(sec_user_id)
                
            except Exception as e:
                utils.logger.error(f"[DouYinCrawler.get_creators_and_videos] Error for {sec_user_id}: {e}")
                
                # 请求失败，更新延迟控制器
                if self.delay_controller:
                    self.delay_controller.on_error()
                
                # 检查是否是验证码导致的错误
                if self.captcha_handler:
                    can_continue = await self.captcha_handler.handle_captcha()
                    if not can_continue:
                        break
        
        utils.logger.info("[DouYinCrawler.get_creators_and_videos] Finished")
