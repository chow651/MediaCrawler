# -*- coding: utf-8 -*-
"""
断点续爬管理模块测试用例
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from tools.checkpoint import CheckpointManager


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """创建临时断点目录"""
    return str(tmp_path / "checkpoint")


@pytest.fixture
def checkpoint_manager(temp_checkpoint_dir):
    """创建断点管理器实例"""
    return CheckpointManager(
        platform="dy",
        crawler_type="search",
        checkpoint_dir=temp_checkpoint_dir,
        save_interval=5,
    )


class TestCheckpointManagerInit:
    """测试初始化"""

    def test_init_creates_directory(self, temp_checkpoint_dir):
        """测试初始化创建目录"""
        assert not os.path.exists(temp_checkpoint_dir)
        CheckpointManager(
            platform="dy",
            crawler_type="search",
            checkpoint_dir=temp_checkpoint_dir,
        )
        assert os.path.exists(temp_checkpoint_dir)

    def test_init_default_values(self, checkpoint_manager):
        """测试默认值"""
        assert checkpoint_manager.platform == "dy"
        assert checkpoint_manager.crawler_type == "search"
        assert checkpoint_manager.save_interval == 5
        assert len(checkpoint_manager.processed_ids) == 0
        assert len(checkpoint_manager.session_ids) == 0
        assert checkpoint_manager.search_offset == 0
        assert checkpoint_manager.current_keyword is None


class TestIsProcessed:
    """测试已处理检查"""

    def test_not_processed(self, checkpoint_manager):
        """测试未处理的 ID"""
        assert not checkpoint_manager.is_processed("id_1")

    def test_processed(self, checkpoint_manager):
        """测试已处理的 ID"""
        checkpoint_manager.processed_ids.add("id_1")
        assert checkpoint_manager.is_processed("id_1")


class TestMarkProcessed:
    """测试标记已处理"""

    def test_mark_single(self, checkpoint_manager):
        """测试标记单个"""
        checkpoint_manager.mark_processed("id_1")
        assert "id_1" in checkpoint_manager.processed_ids
        assert "id_1" in checkpoint_manager.session_ids
        assert checkpoint_manager.ops_count == 1

    def test_mark_multiple(self, checkpoint_manager):
        """测试标记多个"""
        for i in range(3):
            checkpoint_manager.mark_processed(f"id_{i}")
        assert len(checkpoint_manager.processed_ids) == 3
        assert len(checkpoint_manager.session_ids) == 3
        assert checkpoint_manager.ops_count == 3

    def test_auto_save_on_interval(self, checkpoint_manager, temp_checkpoint_dir):
        """测试达到间隔自动保存"""
        # save_interval = 5
        for i in range(5):
            checkpoint_manager.mark_processed(f"id_{i}")

        checkpoint_file = Path(temp_checkpoint_dir) / "dy_search_checkpoint.json"
        assert checkpoint_file.exists()

        with open(checkpoint_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["processed_ids"]) == 5


class TestSetSearchState:
    """测试搜索状态设置"""

    def test_set_search_state(self, checkpoint_manager):
        """测试设置搜索状态"""
        checkpoint_manager.set_search_state("keyword1", 100)
        assert checkpoint_manager.current_keyword == "keyword1"
        assert checkpoint_manager.search_offset == 100

    def test_get_search_offset(self, checkpoint_manager):
        """测试获取搜索偏移量"""
        checkpoint_manager.set_search_state("keyword1", 100)
        assert checkpoint_manager.get_search_offset("keyword1") == 100
        assert checkpoint_manager.get_search_offset("keyword2") == 0


class TestGetStats:
    """测试统计信息"""

    def test_initial_stats(self, checkpoint_manager):
        """测试初始统计"""
        stats = checkpoint_manager.get_stats()
        assert stats["total_processed"] == 0
        assert stats["session_processed"] == 0
        assert stats["search_offset"] == 0
        assert stats["current_keyword"] is None

    def test_stats_after_operations(self, checkpoint_manager):
        """测试操作后的统计"""
        checkpoint_manager.mark_processed("id_1")
        checkpoint_manager.mark_processed("id_2")
        checkpoint_manager.set_search_state("keyword1", 50)

        stats = checkpoint_manager.get_stats()
        assert stats["total_processed"] == 2
        assert stats["session_processed"] == 2
        assert stats["search_offset"] == 50
        assert stats["current_keyword"] == "keyword1"


class TestSaveAndClose:
    """测试保存并关闭"""

    def test_save_and_close(self, checkpoint_manager, temp_checkpoint_dir):
        """测试保存并关闭"""
        checkpoint_manager.mark_processed("id_1")
        checkpoint_manager.mark_processed("id_2")
        checkpoint_manager.save_and_close()

        checkpoint_file = Path(temp_checkpoint_dir) / "dy_search_checkpoint.json"
        assert checkpoint_file.exists()

        with open(checkpoint_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["processed_ids"]) == 2
        assert len(checkpoint_manager.session_ids) == 0

    def test_save_and_close_no_session(self, checkpoint_manager, temp_checkpoint_dir):
        """测试没有会话数据时保存"""
        checkpoint_manager.save_and_close()

        checkpoint_file = Path(temp_checkpoint_dir) / "dy_search_checkpoint.json"
        assert not checkpoint_file.exists()


class TestClear:
    """测试清空断点"""

    def test_clear(self, checkpoint_manager, temp_checkpoint_dir):
        """测试清空"""
        checkpoint_manager.mark_processed("id_1")
        checkpoint_manager.mark_processed("id_2")
        checkpoint_manager.set_search_state("keyword1", 50)
        checkpoint_manager.save_and_close()

        checkpoint_manager.clear()

        assert len(checkpoint_manager.processed_ids) == 0
        assert len(checkpoint_manager.session_ids) == 0
        assert checkpoint_manager.search_offset == 0
        assert checkpoint_manager.current_keyword is None

        checkpoint_file = Path(temp_checkpoint_dir) / "dy_search_checkpoint.json"
        assert not checkpoint_file.exists()


class TestLoadCheckpoint:
    """测试加载断点"""

    def test_load_existing_checkpoint(self, temp_checkpoint_dir):
        """测试加载已存在的断点"""
        # 先创建断点文件
        checkpoint_file = Path(temp_checkpoint_dir) / "dy_search_checkpoint.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "platform": "dy",
            "crawler_type": "search",
            "processed_ids": ["id_1", "id_2", "id_3"],
            "search_offset": 30,
            "current_keyword": "test",
        }
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # 重新加载
        manager = CheckpointManager(
            platform="dy",
            crawler_type="search",
            checkpoint_dir=temp_checkpoint_dir,
        )

        assert len(manager.processed_ids) == 3
        assert manager.search_offset == 30
        assert manager.current_keyword == "test"

    def test_load_nonexistent_checkpoint(self, temp_checkpoint_dir):
        """测试加载不存在的断点"""
        manager = CheckpointManager(
            platform="dy",
            crawler_type="search",
            checkpoint_dir=temp_checkpoint_dir,
        )
        assert len(manager.processed_ids) == 0

    def test_load_corrupted_checkpoint(self, temp_checkpoint_dir):
        """测试加载损坏的断点文件"""
        checkpoint_file = Path(temp_checkpoint_dir) / "dy_search_checkpoint.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            f.write("invalid json")

        manager = CheckpointManager(
            platform="dy",
            crawler_type="search",
            checkpoint_dir=temp_checkpoint_dir,
        )
        assert len(manager.processed_ids) == 0
