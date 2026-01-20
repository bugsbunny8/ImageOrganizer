"""
设置对话框 - 优化版
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from aqt import mw
from aqt.utils import showInfo

from .config import PluginConfig

class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, config: PluginConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.init_ui()
        self.resize(600, 550)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("Image Organizer 设置")
        
        layout = QVBoxLayout()
        
        # 选项卡
        tab_widget = QTabWidget()
        
        # 常规设置
        general_tab = QWidget()
        general_layout = QVBoxLayout()
        
        # 默认命名模式
        general_layout.addWidget(QLabel("默认命名模式:"))
        self.naming_combo = QComboBox()
        for key, value in self.config.naming_patterns.items():
            self.naming_combo.addItem(value, key)
        self.naming_combo.setCurrentText(
            self.config.naming_patterns.get(
                self.config.default_naming_pattern,
                "MD5哈希值"
            )
        )
        general_layout.addWidget(self.naming_combo)
        
        # 自定义命名模式
        general_layout.addWidget(QLabel("自定义命名模式:"))
        self.custom_pattern_edit = QLineEdit(self.config.default_file_pattern)
        self.custom_pattern_edit.setPlaceholderText("img_{hash}{ext}")
        general_layout.addWidget(self.custom_pattern_edit)
        
        # 默认范围
        general_layout.addWidget(QLabel("默认扫描范围:"))
        self.scope_combo = QComboBox()
        for key, value in self.config.scan_scope.scope_options.items():
            self.scope_combo.addItem(value, key)
        self.scope_combo.setCurrentText(
            self.config.scan_scope.scope_options.get(
                self.config.scan_scope.default_scope,
                "当前牌组"
            )
        )
        general_layout.addWidget(self.scope_combo)
        
        # 包含子牌组
        self.include_subdecks_check = QCheckBox("默认包含子牌组")
        self.include_subdecks_check.setChecked(self.config.scan_scope.include_subdecks)
        general_layout.addWidget(self.include_subdecks_check)
        
        # 自动备份
        self.auto_backup_check = QCheckBox("自动备份")
        self.auto_backup_check.setChecked(self.config.auto_backup)
        general_layout.addWidget(self.auto_backup_check)
        
        # 备份文件夹
        general_layout.addWidget(QLabel("备份文件夹:"))
        backup_layout = QHBoxLayout()
        self.backup_folder_edit = QLineEdit(self.config.backup_folder)
        backup_layout.addWidget(self.backup_folder_edit)
        self.backup_browse_button = QPushButton("浏览...")
        self.backup_browse_button.clicked.connect(self.browse_backup_folder)
        backup_layout.addWidget(self.backup_browse_button)
        general_layout.addLayout(backup_layout)
        
        general_layout.addStretch()
        general_tab.setLayout(general_layout)
        
        # 扫描设置
        scanning_tab = QWidget()
        scanning_layout = QVBoxLayout()
        
        # 扫描时计算哈希
        self.calculate_hash_check = QCheckBox("扫描时计算文件哈希")
        self.calculate_hash_check.setChecked(True)
        self.calculate_hash_check.setToolTip("扫描时计算文件哈希值用于生成新文件名，禁用可提高扫描速度但无法预估新文件名")
        scanning_layout.addWidget(self.calculate_hash_check)
        
        # 快速哈希计算
        self.fast_hash_check = QCheckBox("使用快速哈希计算")
        self.fast_hash_check.setChecked(True)
        self.fast_hash_check.setToolTip("只读取文件部分内容计算哈希，速度更快但可能有极小概率的哈希冲突")
        scanning_layout.addWidget(self.fast_hash_check)
        
        # 预估节省空间
        self.estimate_savings_check = QCheckBox("扫描时预估节省空间")
        self.estimate_savings_check.setChecked(True)
        self.estimate_savings_check.setToolTip("扫描时根据文件类型预估优化后可以节省的空间")
        scanning_layout.addWidget(self.estimate_savings_check)
        
        # 批处理大小
        scanning_layout.addWidget(QLabel("批处理大小:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(10, 1000)
        self.batch_size_spin.setValue(self.config.batch_size)
        self.batch_size_spin.setSuffix(" 张卡片/批")
        scanning_layout.addWidget(self.batch_size_spin)
        
        # 最大处理卡片数
        scanning_layout.addWidget(QLabel("最大处理卡片数:"))
        self.max_cards_spin = QSpinBox()
        self.max_cards_spin.setRange(0, 100000)
        self.max_cards_spin.setValue(self.config.max_cards_to_process)
        self.max_cards_spin.setSpecialValueText("无限制")
        scanning_layout.addWidget(self.max_cards_spin)
        
        scanning_layout.addStretch()
        scanning_tab.setLayout(scanning_layout)
        
        # 处理设置
        processing_tab = QWidget()
        processing_layout = QVBoxLayout()
        
        # 超时时间
        processing_layout.addWidget(QLabel("处理超时时间:"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 3600)
        self.timeout_spin.setValue(self.config.timeout_seconds)
        self.timeout_spin.setSuffix(" 秒")
        processing_layout.addWidget(self.timeout_spin)
        
        # 跳过锁定卡片
        self.skip_locked_check = QCheckBox("跳过已锁定的卡片")
        self.skip_locked_check.setChecked(self.config.skip_locked_cards)
        processing_layout.addWidget(self.skip_locked_check)
        
        processing_layout.addStretch()
        processing_tab.setLayout(processing_layout)
        
        # 历史记录
        history_tab = QWidget()
        history_layout = QVBoxLayout()
        
        # 清除历史记录
        history_layout.addWidget(QLabel("历史记录设置:"))
        
        self.clear_searches_button = QPushButton("清除搜索历史")
        self.clear_searches_button.clicked.connect(self.clear_search_history)
        history_layout.addWidget(self.clear_searches_button)
        
        self.clear_decks_button = QPushButton("清除牌组选择历史")
        self.clear_decks_button.clicked.connect(self.clear_deck_history)
        history_layout.addWidget(self.clear_decks_button)
        
        history_layout.addStretch()
        
        # 历史记录最大数量
        history_layout.addWidget(QLabel("最大历史记录数量:"))
        self.history_max_spin = QSpinBox()
        self.history_max_spin.setRange(5, 100)
        self.history_max_spin.setValue(self.config.scan_scope.max_history)
        history_layout.addWidget(self.history_max_spin)
        
        history_tab.setLayout(history_layout)
        
        # 添加选项卡
        tab_widget.addTab(general_tab, "常规")
        tab_widget.addTab(scanning_tab, "扫描")
        tab_widget.addTab(processing_tab, "处理")
        tab_widget.addTab(history_tab, "历史记录")
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("恢复默认")
        self.reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def browse_backup_folder(self):
        """选择备份文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择备份文件夹",
            self.backup_folder_edit.text()
        )
        if folder:
            self.backup_folder_edit.setText(folder)
    
    def clear_search_history(self):
        """清除搜索历史"""
        self.config.scan_scope.recent_searches = []
        showInfo("搜索历史已清除")
    
    def clear_deck_history(self):
        """清除牌组选择历史"""
        self.config.scan_scope.recent_decks = []
        showInfo("牌组选择历史已清除")
    
    def save_settings(self):
        """保存设置"""
        # 更新配置
        self.config.default_naming_pattern = self.naming_combo.currentData()
        self.config.default_file_pattern = self.custom_pattern_edit.text()
        self.config.scan_scope.default_scope = self.scope_combo.currentData()
        self.config.scan_scope.include_subdecks = self.include_subdecks_check.isChecked()
        self.config.auto_backup = self.auto_backup_check.isChecked()
        self.config.backup_folder = self.backup_folder_edit.text()
        self.config.batch_size = self.batch_size_spin.value()
        self.config.max_cards_to_process = self.max_cards_spin.value()
        self.config.timeout_seconds = self.timeout_spin.value()
        self.config.skip_locked_cards = self.skip_locked_check.isChecked()
        self.config.scan_scope.max_history = self.history_max_spin.value()
        
        showInfo("设置已保存")
        self.accept()
    
    def reset_to_default(self):
        """恢复默认设置"""
        from .config import PluginConfig
        default_config = PluginConfig()
        
        # 更新UI
        self.naming_combo.setCurrentText(
            default_config.naming_patterns.get(
                default_config.default_naming_pattern,
                "MD5哈希值"
            )
        )
        self.custom_pattern_edit.setText(default_config.default_file_pattern)
        self.scope_combo.setCurrentText(
            default_config.scan_scope.scope_options.get(
                default_config.scan_scope.default_scope,
                "当前牌组"
            )
        )
        self.include_subdecks_check.setChecked(default_config.scan_scope.include_subdecks)
        self.auto_backup_check.setChecked(default_config.auto_backup)
        self.backup_folder_edit.setText(default_config.backup_folder)
        self.batch_size_spin.setValue(default_config.batch_size)
        self.max_cards_spin.setValue(default_config.max_cards_to_process)
        self.timeout_spin.setValue(default_config.timeout_seconds)
        self.skip_locked_check.setChecked(default_config.skip_locked_cards)
        self.history_max_spin.setValue(default_config.scan_scope.max_history)
        
        showInfo("已恢复默认设置")