"""
配置管理 - 完整版
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Set

@dataclass
class CompressionConfig:
    """压缩配置"""
    
    # JPG压缩质量 (1-100)
    jpg_quality: int = 85
    
    # 是否启用有损压缩
    enable_lossy_compression: bool = True
    
    # 最小压缩率阈值 (只有压缩后文件小于原文件比例时才转换)
    min_compression_ratio: float = 0.9
    
    # 目标格式优先级
    format_priority: List[str] = field(default_factory=lambda: [
        'jpg', 'webp', 'png'
    ]
    )

    # 最小处理文件大小（KB），只有大于等于此值的文件才会被处理
    min_file_size_kb: int = 1024

@dataclass
class ResolutionConfig:
    """分辨率配置"""
    
    # 预设分辨率
    presets: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        "mobile": (720, 1280),      # 手机优化
        "tablet": (1080, 1920),     # 平板优化
        "laptop": (1366, 768),      # 笔记本优化
        "1080p": (1920, 1080),      # 全高清
        "1440p": (2560, 1440),      # 2K
        "4k": (3840, 2160),         # 4K
        "original": (0, 0)          # 保持原样
    })
    
    # 默认预设
    default_preset: str = "laptop"
    
    # 最大尺寸限制 (0表示无限制)
    max_width: int = 3840
    max_height: int = 2160
    
    # 是否保持宽高比
    keep_aspect_ratio: bool = True
    
    # 缩放模式: contain, cover, fill
    resize_mode: str = "contain"

@dataclass
class ScanScopeConfig:
    """扫描范围配置"""
    
    # 范围选项
    scope_options: Dict[str, str] = field(default_factory=lambda: {
        "all": "所有卡片",
        "current_deck": "当前牌组",
        "selected_decks": "指定牌组",
        "selected_cards": "选中卡片",
        "custom_search": "自定义搜索"
    })
    
    # 默认范围
    default_scope: str = "current_deck"
    
    # 是否包含子牌组
    include_subdecks: bool = True
    
    # 最近使用的搜索条件
    recent_searches: List[str] = field(default_factory=list)
    
    # 最近选择的牌组
    recent_decks: List[str] = field(default_factory=list)
    
    # 最大历史记录数量
    max_history: int = 10
    
    # 自定义搜索模板
    search_templates: Dict[str, str] = field(default_factory=lambda: {
        "recently_added": "added:7",  # 最近7天添加
        "with_images": "tag:has_image",  # 有图片标签的卡片
        "large_images": "tag:large_image",  # 有大图的卡片
        "by_note_type": "note:basic",  # 特定笔记类型
    })

@dataclass
class PluginConfig:
    """插件配置类 - 完整版"""
    
    # 扫描范围配置
    scan_scope: ScanScopeConfig = field(default_factory=ScanScopeConfig)
    
    # 命名模式选项
    naming_patterns: Dict[str, str] = field(default_factory=lambda: {
        "hash": "MD5哈希值",
        "timestamp": "时间戳",
        "sequence": "顺序编号",
        "custom": "自定义模式"
    })
    
    # 默认配置
    default_naming_pattern: str = "hash"
    default_file_pattern: str = "img_{hash}{ext}"
    
    # 图片扩展名
    image_extensions: List[str] = field(default_factory=lambda: [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.tiff', '.tif', '.webp', '.svg', '.heic', '.heif'
    ])
    
    # 支持转换的格式
    convertible_formats: List[str] = field(default_factory=lambda: [
        'png', 'bmp', 'tiff', 'tif', 'webp', 'heic', 'heif'
    ])
    
    # 目标输出格式
    target_format: str = 'jpg'
    
    # 正则表达式模式匹配图片标签
    img_patterns: List[str] = field(default_factory=lambda: [
        r'<img[^>]+src="([^"]+)"[^>]*>',
        r'\[sound:([^\]]+)\]',
        r'src="([^"]+)"',
    ])
    
    # 是否自动备份
    auto_backup: bool = True
    backup_folder: str = "anki_image_backups"
    
    # 忽略的模式
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "http://", "https://", "data:image"
    ])
    
    # 压缩配置
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    
    # 分辨率配置
    resolution: ResolutionConfig = field(default_factory=ResolutionConfig)
    
    # 处理策略
    optimization_strategy: str = "balanced"  # minimal, balanced, aggressive
    
    # 元数据保留选项
    preserve_metadata: bool = False
    preserve_exif: bool = True
    
    # 高级选项
    skip_locked_cards: bool = True  # 跳过已锁定的卡片
    batch_size: int = 100  # 批处理大小
    max_cards_to_process: int = 10000  # 最大处理卡片数
    timeout_seconds: int = 300  # 超时时间（秒）
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保备份文件夹存在
        backup_path = Path(self.backup_folder)
        if not backup_path.exists():
            backup_path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "default_naming_pattern": self.default_naming_pattern,
            "default_file_pattern": self.default_file_pattern,
            "target_format": self.target_format,
            "auto_backup": self.auto_backup,
            "backup_folder": self.backup_folder,
            "optimization_strategy": self.optimization_strategy,
            "preserve_metadata": self.preserve_metadata,
            "skip_locked_cards": self.skip_locked_cards,
            "batch_size": self.batch_size,
            "max_cards_to_process": self.max_cards_to_process,
            "timeout_seconds": self.timeout_seconds,
            "scan_scope": {
                "default_scope": self.scan_scope.default_scope,
                "include_subdecks": self.scan_scope.include_subdecks,
                "recent_searches": self.scan_scope.recent_searches[:self.scan_scope.max_history],
                "recent_decks": self.scan_scope.recent_decks[:self.scan_scope.max_history],
            },
            "compression": {
                "jpg_quality": self.compression.jpg_quality,
                "enable_lossy_compression": self.compression.enable_lossy_compression,
                "min_compression_ratio": self.compression.min_compression_ratio,
                "min_file_size_kb": self.compression.min_file_size_kb,
            },
            "resolution": {
                "default_preset": self.resolution.default_preset,
                "max_width": self.resolution.max_width,
                "max_height": self.resolution.max_height,
                "keep_aspect_ratio": self.resolution.keep_aspect_ratio,
                "resize_mode": self.resolution.resize_mode,
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginConfig':
        """从字典创建配置"""
        config = cls()
        if data:
            # 基础配置
            config.default_naming_pattern = data.get("default_naming_pattern", 
                                                    config.default_naming_pattern)
            config.default_file_pattern = data.get("default_file_pattern",
                                                  config.default_file_pattern)
            config.target_format = data.get("target_format", config.target_format)
            config.auto_backup = data.get("auto_backup", config.auto_backup)
            config.backup_folder = data.get("backup_folder", config.backup_folder)
            config.optimization_strategy = data.get("optimization_strategy", 
                                                   config.optimization_strategy)
            config.preserve_metadata = data.get("preserve_metadata", 
                                               config.preserve_metadata)
            config.skip_locked_cards = data.get("skip_locked_cards",
                                               config.skip_locked_cards)
            config.batch_size = data.get("batch_size", config.batch_size)
            config.max_cards_to_process = data.get("max_cards_to_process",
                                                  config.max_cards_to_process)
            config.timeout_seconds = data.get("timeout_seconds",
                                             config.timeout_seconds)
            
            # 扫描范围配置
            scan_scope_data = data.get("scan_scope", {})
            if scan_scope_data:
                config.scan_scope.default_scope = scan_scope_data.get("default_scope",
                                                                     config.scan_scope.default_scope)
                config.scan_scope.include_subdecks = scan_scope_data.get("include_subdecks",
                                                                        config.scan_scope.include_subdecks)
                config.scan_scope.recent_searches = scan_scope_data.get("recent_searches",
                                                                       config.scan_scope.recent_searches)
                config.scan_scope.recent_decks = scan_scope_data.get("recent_decks",
                                                                    config.scan_scope.recent_decks)
            
            # 压缩配置
            compression_data = data.get("compression", {})
            if compression_data:
                config.compression.jpg_quality = compression_data.get("jpg_quality", 
                                                                     config.compression.jpg_quality)
                config.compression.enable_lossy_compression = compression_data.get(
                    "enable_lossy_compression", config.compression.enable_lossy_compression)
                config.compression.min_compression_ratio = compression_data.get(
                    "min_compression_ratio", config.compression.min_compression_ratio)
                config.compression.min_file_size_kb = compression_data.get(
                    "min_file_size_kb", config.compression.min_file_size_kb)
            
            # 分辨率配置
            resolution_data = data.get("resolution", {})
            if resolution_data:
                config.resolution.default_preset = resolution_data.get("default_preset",
                                                                      config.resolution.default_preset)
                config.resolution.max_width = resolution_data.get("max_width",
                                                                 config.resolution.max_width)
                config.resolution.max_height = resolution_data.get("max_height",
                                                                  config.resolution.max_height)
                config.resolution.keep_aspect_ratio = resolution_data.get("keep_aspect_ratio",
                                                                         config.resolution.keep_aspect_ratio)
                config.resolution.resize_mode = resolution_data.get("resize_mode",
                                                                   config.resolution.resize_mode)
        
        return config
    
    def get_resolution_preset(self, preset_name: str) -> Tuple[int, int]:
        """获取分辨率预设"""
        return self.resolution.presets.get(preset_name, (0, 0))

class Config:
    """配置管理器"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent / "config.json"
        self.default_config = PluginConfig()
        self.current_config = self.load_config()
    
    def get_config(self) ->PluginConfig:
        return self.current_config
    
    def load_config(self) -> PluginConfig:
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return PluginConfig.from_dict(data)
            except Exception as e:
                print(f"加载配置失败: {e}")
                return self.default_config
        return self.default_config
    
    def save_config(self) -> bool:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_config.to_dict(), f, 
                         indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            # 嵌套配置处理
            if '.' in key:
                parts = key.split('.')
                obj = self.current_config
                for part in parts[:-1]:
                    if hasattr(obj, part):
                        obj = getattr(obj, part)
                    else:
                        break
                if hasattr(obj, parts[-1]):
                    setattr(obj, parts[-1], value)
            else:
                if hasattr(self.current_config, key):
                    setattr(self.current_config, key, value)
        self.save_config()
    
    def reset_to_default(self):
        """重置为默认配置"""
        self.current_config = PluginConfig()
        self.save_config()