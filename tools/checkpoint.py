# -*- coding: utf-8 -*-
"""
断点续爬模块
记录已爬取的数据ID，支持中断后从断点继续
"""

import json
import os
import time
from pathlib import Path
from typing import Optional, Set
from tools import utils


class CheckpointManager:
    """断点续爬管理器"""
    
    def __init__(
        self,
        platform: str,
        crawler_type: str,
        checkpoint_dir: str = "checkpoint",
        save_interval: int = 10,
    ):
        """
        Args:
            platform: 平台标识 (dy, xhs, ks, etc.)
            crawler_type: 爬取类型 (search, detail, creator)
            checkpoint_dir: 断点文件存储目录
            save_interval: 每处理多少条记录保存一次断点
        """
        self.platform = platform
        self.crawler_type = crawler_type
        self.checkpoint_dir = Path(checkpoint_dir)
        self.save_interval = save_interval
        
        # 已处理的ID集合
        self.processed_ids: Set[str] = set()
        # 当前会话新增的ID
        self.session_ids: Set[str] = set()
        # 当前关键词（用于搜索模式）
        self.current_keyword: Optional[str] = None
        # 搜索模式的偏移量
        self.search_offset: int = 0
        # 最后保存时间
        self.last_save_time: float = 0.0
        # 操作计数
        self.ops_count: int = 0
        
        # 确保目录存在
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载已有断点
        self._load_checkpoint()
    
    def _get_checkpoint_file(self) -> Path:
        """获取断点文件路径"""
        filename = f"{self.platform}_{self.crawler_type}_checkpoint.json"
        return self.checkpoint_dir / filename
    
    def _load_checkpoint(self):
        """加载断点文件"""
        checkpoint_file = self._get_checkpoint_file()
        
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self.processed_ids = set(data.get("processed_ids", []))
                self.search_offset = data.get("search_offset", 0)
                self.current_keyword = data.get("current_keyword")
                
                utils.logger.info(
                    f"[Checkpoint] 加载断点成功: {len(self.processed_ids)} 个已处理ID, "
                    f"偏移量: {self.search_offset}"
                )
            except Exception as e:
                utils.logger.warning(f"[Checkpoint] 加载断点失败: {e}")
                self.processed_ids = set()
    
    def _save_checkpoint(self):
        """保存断点文件"""
        checkpoint_file = self._get_checkpoint_file()
        
        try:
            data = {
                "platform": self.platform,
                "crawler_type": self.crawler_type,
                "processed_ids": list(self.processed_ids),
                "search_offset": self.search_offset,
                "current_keyword": self.current_keyword,
                "last_save_time": time.time(),
                "total_count": len(self.processed_ids),
            }
            
            # 先写入临时文件，再重命名，避免写入中断导致文件损坏
            temp_file = checkpoint_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            temp_file.replace(checkpoint_file)
            self.last_save_time = time.time()
            self.session_ids.clear()
            
            utils.logger.debug(
                f"[Checkpoint] 保存断点成功: {len(self.processed_ids)} 个ID"
            )
        except Exception as e:
            utils.logger.error(f"[Checkpoint] 保存断点失败: {e}")
    
    def is_processed(self, item_id: str) -> bool:
        """检查ID是否已处理"""
        return item_id in self.processed_ids
    
    def mark_processed(self, item_id: str):
        """标记ID为已处理"""
        self.processed_ids.add(item_id)
        self.session_ids.add(item_id)
        self.ops_count += 1
        
        # 达到保存间隔时自动保存
        if self.ops_count % self.save_interval == 0:
            self._save_checkpoint()
    
    def set_search_state(self, keyword: str, offset: int):
        """设置搜索状态"""
        self.current_keyword = keyword
        self.search_offset = offset
    
    def get_search_offset(self, keyword: str) -> int:
        """获取指定关键词的搜索偏移量"""
        if self.current_keyword == keyword:
            return self.search_offset
        return 0
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_processed": len(self.processed_ids),
            "session_processed": len(self.session_ids),
            "search_offset": self.search_offset,
            "current_keyword": self.current_keyword,
        }
    
    def save_and_close(self):
        """保存并关闭"""
        if self.session_ids:
            self._save_checkpoint()
            utils.logger.info(
                f"[Checkpoint] 最终保存: 本次会话处理 {len(self.session_ids)} 个ID, "
                f"总计 {len(self.processed_ids)} 个ID"
            )
    
    def clear(self):
        """清空断点"""
        self.processed_ids.clear()
        self.session_ids.clear()
        self.search_offset = 0
        self.current_keyword = None
        
        checkpoint_file = self._get_checkpoint_file()
        if checkpoint_file.exists():
            checkpoint_file.unlink()
        
        utils.logger.info("[Checkpoint] 断点已清空")

