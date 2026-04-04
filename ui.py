"""
用户界面 - 优化版，支持滚动区域和预估信息
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
import re
import time

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from aqt import mw
from aqt.utils import showInfo, showWarning, askUser, tooltip

from .scanner import CardScanner, ScanScope, ImageReference
from .processor import ImageProcessor
from .config import PluginConfig

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class EstimateThread(QThread):
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, scanner, scan_scope, parent=None):
        super().__init__(parent)
        self.scanner = scanner
        self.scan_scope = scan_scope
        
    def run(self):
        try:
            estimate = self.scanner.estimate_scope_size(self.scan_scope)
            self.finished_signal.emit(estimate)
        except Exception as e:
            self.error_signal.emit(str(e))

class ScanThread(QThread):
    finished_signal = pyqtSignal(list, dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, scanner, scan_scope, parent=None):
        super().__init__(parent)
        self.scanner = scanner
        self.scan_scope = scan_scope
        
    def run(self):
        try:
            start_time = time.time()
            cards = self.scanner.scan_scope(self.scan_scope)
            stats = self.scanner.get_statistics(cards)
            stats['scan_time_seconds'] = time.time() - start_time
            self.finished_signal.emit(cards, stats)
        except Exception as e:
            self.error_signal.emit(str(e))


class DeckSelectionDialog(QDialog):
    """牌组选择对话框"""
    
    def __init__(self, deck_list: List[Dict], selected_decks: Set[int] = None, include_subdecks: bool = False, parent=None):
        super().__init__(parent)
        self.deck_list = deck_list
        self.selected_decks = selected_decks or set()
        self.include_subdecks = include_subdecks
        self.init_ui()
        self.resize(500, 600)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("选择牌组")
        
        layout = QVBoxLayout()
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索牌组:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入牌组名称...")
        self.search_edit.textChanged.connect(self.filter_decks)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        
        # 包含子牌组复选框（布局到搜索框最右边）
        self.include_subdecks_check = QCheckBox("包含子牌组")
        self.include_subdecks_check.setChecked(self.include_subdecks)
        search_layout.addWidget(self.include_subdecks_check)
        
        layout.addLayout(search_layout)
        
        # 牌组树
        self.deck_tree = QTreeWidget()
        self.deck_tree.setHeaderLabel("牌组列表")
        self.deck_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        self.deck_tree.setRootIsDecorated(True)
        self.deck_tree.setIndentation(20)
        layout.addWidget(self.deck_tree)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_button)
        
        self.deselect_all_button = QPushButton("全不选")
        self.deselect_all_button.clicked.connect(self.deselect_all)
        button_layout.addWidget(self.deselect_all_button)
        
        button_layout.addStretch()
        
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # 加载牌组
        self.load_decks()
        
        # 连接项目状态改变信号
        self.deck_tree.itemChanged.connect(self.on_item_changed)
    
    def load_decks(self):
        """加载牌组到树中"""
        self.deck_tree.clear()
        
        # 创建牌组树结构
        deck_nodes = {}
        
        # 第一次遍历：创建所有节点
        for deck in self.deck_list:
            deck_id = deck['id']
            deck_name = deck['name']
            
            # 创建树节点，显示真实卡片数
            item = QTreeWidgetItem([f"{deck_name} ({deck['card_count']} 张卡片)"])
            item.setData(0, Qt.ItemDataRole.UserRole, deck_id)

            # 设置选择状态
            if deck_id in self.selected_decks:
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            
            # 存储节点
            deck_nodes[deck_name] = item
            
            # 如果有父级，添加到父级
            parent_name = deck['parent']
            if parent_name and parent_name in deck_nodes:
                deck_nodes[parent_name].addChild(item)
            else:
                self.deck_tree.addTopLevelItem(item)
        
        # 展开所有节点
        self.deck_tree.expandAll()
    
    def on_item_changed(self, item: QTreeWidgetItem, column: int):
        """处理树节点状态改变"""
        if getattr(self, '_updating_items', False) or not self.include_subdecks_check.isChecked():
            return
            
        checked = item.checkState(0) == Qt.CheckState.Checked
        for i in range(item.childCount()):
            child = item.child(i)
            self._set_item_checked(child, checked)
    
    def filter_decks(self, text: str):
        """过滤牌组"""
        text = text.lower()
        
        for i in range(self.deck_tree.topLevelItemCount()):
            item = self.deck_tree.topLevelItem(i)
            self._filter_item(item, text)
    
    def _filter_item(self, item: QTreeWidgetItem, text: str):
        """过滤单个项目"""
        item_text = item.text(0).lower()
        has_match = text in item_text
        
        # 检查子项目
        child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            child_has_match = self._filter_item(child, text)
            child_visible = child_visible or child_has_match
        
        # 显示或隐藏项目
        item.setHidden(not (has_match or child_visible))
        
        return has_match or child_visible
    
    def select_all(self):
        """全选"""
        for i in range(self.deck_tree.topLevelItemCount()):
            item = self.deck_tree.topLevelItem(i)
            self._set_item_checked(item, True)
    
    def deselect_all(self):
        """全不选"""
        for i in range(self.deck_tree.topLevelItemCount()):
            item = self.deck_tree.topLevelItem(i)
            self._set_item_checked(item, False)
    
    def _set_item_checked(self, item: QTreeWidgetItem, checked: bool):
        """设置项目选择状态"""
        was_updating = getattr(self, '_updating_items', False)
        self._updating_items = True
        try:
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            
            # 递归设置子项目
            for i in range(item.childCount()):
                child = item.child(i)
                self._set_item_checked(child, checked)
        finally:
            self._updating_items = was_updating
    
    def get_selected_decks(self) -> Set[int]:
        """获取选中的牌组ID"""
        selected = set()
        
        for i in range(self.deck_tree.topLevelItemCount()):
            item = self.deck_tree.topLevelItem(i)
            self._collect_selected(item, selected)
        
        return selected
    
    def _collect_selected(self, item: QTreeWidgetItem, selected: Set[int]):
        """收集选中的牌组ID"""
        if item.checkState(0) == Qt.CheckState.Checked:
            deck_id = item.data(0, Qt.ItemDataRole.UserRole)
            if deck_id:
                selected.add(deck_id)
        
        # 递归收集子项目
        for i in range(item.childCount()):
            child = item.child(i)
            self._collect_selected(child, selected)


class OptimizationOptionsDialog(QDialog):
    """优化选项对话框"""
    
    def __init__(self, config: PluginConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.init_ui()
        self.resize(500, 400)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("图片优化选项")
        
        layout = QVBoxLayout()
        
        # 格式转换选项
        format_group = QGroupBox("格式转换")
        format_layout = QVBoxLayout()
        
        # 启用格式转换
        self.enable_conversion_check = QCheckBox("启用格式转换")
        self.enable_conversion_check.setChecked(True)
        format_layout.addWidget(self.enable_conversion_check)
        
        # 目标格式
        format_layout.addWidget(QLabel("目标格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(['JPG (推荐)', 'WebP', 'PNG'])
        self.format_combo.setCurrentText('JPG (推荐)')
        format_layout.addWidget(self.format_combo)
        
        # JPG质量
        format_layout.addWidget(QLabel("JPG压缩质量 (1-100):"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(self.config.compression.jpg_quality)
        self.quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.quality_slider.setTickInterval(10)
        format_layout.addWidget(self.quality_slider)
        
        self.quality_label = QLabel(f"{self.config.compression.jpg_quality}")
        format_layout.addWidget(self.quality_label)
        
        # 连接信号
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_label.setText(f"{v}")
        )
        
        # 最小压缩率
        format_layout.addWidget(QLabel("最小压缩率阈值:"))
        self.compression_threshold_spin = QDoubleSpinBox()
        self.compression_threshold_spin.setRange(0.1, 1.0)
        self.compression_threshold_spin.setSingleStep(0.05)
        self.compression_threshold_spin.setValue(
            self.config.compression.min_compression_ratio
        )
        self.compression_threshold_spin.setSuffix(" (原文件比例)")
        format_layout.addWidget(self.compression_threshold_spin)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 分辨率选项
        resolution_group = QGroupBox("分辨率调整")
        resolution_layout = QGridLayout()
        
        # 启用分辨率调整
        self.enable_resize_check = QCheckBox("调整分辨率")
        self.enable_resize_check.setChecked(True)
        resolution_layout.addWidget(self.enable_resize_check, 0, 0, 1, 2)
        
        # 预设选择
        resolution_layout.addWidget(QLabel("预设分辨率:"), 1, 0)
        self.preset_combo = QComboBox()
        for preset_name, (width, height) in self.config.resolution.presets.items():
            if preset_name == "original":
                display_name = "保持原样"
            else:
                display_name = f"{preset_name} ({width}x{height})"
            self.preset_combo.addItem(display_name, preset_name)
        
        current_preset = self.config.resolution.default_preset
        index = self.preset_combo.findData(current_preset)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        
        resolution_layout.addWidget(self.preset_combo, 1, 1)
        
        # 自定义分辨率
        self.custom_width_edit = QSpinBox()
        self.custom_width_edit.setRange(1, 7680)
        self.custom_width_edit.setValue(1920)
        self.custom_width_edit.setPrefix("宽度: ")
        self.custom_width_edit.setSuffix(" px")
        
        self.custom_height_edit = QSpinBox()
        self.custom_height_edit.setRange(1, 4320)
        self.custom_height_edit.setValue(1080)
        self.custom_height_edit.setPrefix("高度: ")
        self.custom_height_edit.setSuffix(" px")
        
        self.custom_resolution_check = QCheckBox("自定义分辨率")
        resolution_layout.addWidget(self.custom_resolution_check, 2, 0, 1, 2)
        resolution_layout.addWidget(self.custom_width_edit, 3, 0)
        resolution_layout.addWidget(self.custom_height_edit, 3, 1)
        
        # 缩放模式
        resolution_layout.addWidget(QLabel("缩放模式:"), 4, 0)
        self.resize_mode_combo = QComboBox()
        self.resize_mode_combo.addItems(["保持宽高比 (contain)", "覆盖 (cover)", "拉伸填充 (fill)"])
        resolution_layout.addWidget(self.resize_mode_combo, 4, 1)
        
        # 保持宽高比
        self.keep_aspect_check = QCheckBox("保持宽高比")
        self.keep_aspect_check.setChecked(self.config.resolution.keep_aspect_ratio)
        resolution_layout.addWidget(self.keep_aspect_check, 5, 0, 1, 2)
        
        resolution_group.setLayout(resolution_layout)
        layout.addWidget(resolution_group)

        # 文件大小限制选项
        size_group = QGroupBox("文件大小限制")
        size_layout = QVBoxLayout()
        
        self.enable_size_limit_check = QCheckBox("启用文件大小限制（仅处理大于阈值的图片）")
        self.enable_size_limit_check.setChecked(self.config.compression.min_file_size_kb > 0)
        size_layout.addWidget(self.enable_size_limit_check)
        
        size_limit_layout = QHBoxLayout()
        size_limit_layout.addWidget(QLabel("最小处理大小:"))
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(0, 102400)  # 0-100MB
        self.min_size_spin.setValue(self.config.compression.min_file_size_kb)
        self.min_size_spin.setSuffix(" KB")
        self.min_size_spin.setEnabled(self.config.compression.min_file_size_kb > 0)
        size_limit_layout.addWidget(self.min_size_spin)
        
        self.enable_size_limit_check.toggled.connect(
            lambda checked: self.min_size_spin.setEnabled(checked)
        )
        
        size_limit_layout.addStretch()
        size_layout.addLayout(size_limit_layout)
        
        size_group.setLayout(size_layout)
        layout.addWidget(size_group)

        # 按钮
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def get_options(self) -> Dict:
        """获取选项"""
        target_format = "jpg"
        format_text = self.format_combo.currentText()
        if "WebP" in format_text:
            target_format = "webp"
        elif "PNG" in format_text:
            target_format = "png"
        
        # 分辨率
        if self.custom_resolution_check.isChecked():
            resolution = (self.custom_width_edit.value(), self.custom_height_edit.value())
            preset_name = "custom"
        else:
            preset_name = self.preset_combo.currentData()
            resolution = self.config.get_resolution_preset(preset_name)
        
        # 缩放模式
        resize_mode_text = self.resize_mode_combo.currentText()
        if "contain" in resize_mode_text:
            resize_mode = "contain"
        elif "cover" in resize_mode_text:
            resize_mode = "cover"
        else:
            resize_mode = "fill"
        
        # 文件大小限制
        min_file_size_kb = self.min_size_spin.value() if self.enable_size_limit_check.isChecked() else 0

        return {
            'enable_conversion': self.enable_conversion_check.isChecked(),
            'target_format': target_format,
            'jpg_quality': self.quality_slider.value(),
            'min_compression_ratio': self.compression_threshold_spin.value(),
            'enable_resize': self.enable_resize_check.isChecked(),
            'resolution_preset': preset_name,
            'resolution': resolution,
            'resize_mode': resize_mode,
            'keep_aspect_ratio': self.keep_aspect_check.isChecked(),
            'min_file_size_kb': min_file_size_kb
        }


class ScanScopeWidget(QWidget):
    """扫描范围选择组件"""
    
    def __init__(self, config: PluginConfig, scanner: CardScanner, parent=None):
        super().__init__(parent)
        self.config = config
        self.scanner = scanner
        self.selected_decks = set()
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 范围选择标签
        layout.addWidget(QLabel("选择扫描范围:"))
        
        # 范围选项按钮组
        self.scope_group = QButtonGroup(self)
        
        # 所有卡片
        self.all_cards_radio = QRadioButton("所有卡片")
        self.all_cards_radio.setChecked(self.config.scan_scope.default_scope == "all")
        self.scope_group.addButton(self.all_cards_radio, 0)
        layout.addWidget(self.all_cards_radio)
        
        # 当前牌组
        self.current_deck_radio = QRadioButton("当前牌组")
        self.current_deck_radio.setChecked(self.config.scan_scope.default_scope == "current_deck")
        self.scope_group.addButton(self.current_deck_radio, 1)
        layout.addWidget(self.current_deck_radio)
        
        # 指定牌组
        self.selected_decks_radio = QRadioButton("指定牌组")
        self.selected_decks_radio.setChecked(self.config.scan_scope.default_scope == "selected_decks")
        self.scope_group.addButton(self.selected_decks_radio, 2)
        
        decks_layout = QHBoxLayout()
        decks_layout.addWidget(self.selected_decks_radio)
        
        self.deck_select_button = QPushButton("选择牌组...")
        self.deck_select_button.clicked.connect(self.select_decks)
        decks_layout.addWidget(self.deck_select_button)
        
        self.deck_count_label = QLabel("(未选择)")
        decks_layout.addWidget(self.deck_count_label)
        
        # 内部状态变量代替界面复选框
        self.include_subdecks = self.config.scan_scope.include_subdecks
        
        decks_layout.addStretch()
        layout.addLayout(decks_layout)
        
        # 选中卡片
        self.selected_cards_radio = QRadioButton("选中卡片（从卡片浏览器）")
        self.selected_cards_radio.setChecked(self.config.scan_scope.default_scope == "selected_cards")
        self.scope_group.addButton(self.selected_cards_radio, 3)
        layout.addWidget(self.selected_cards_radio)
        
        # 自定义搜索
        self.custom_search_radio = QRadioButton("自定义搜索")
        self.custom_search_radio.setChecked(self.config.scan_scope.default_scope == "custom_search")
        self.scope_group.addButton(self.custom_search_radio, 4)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.custom_search_radio)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入Anki搜索条件，如：deck:法语 tag:动词")
        self.search_edit.setText(self.config.scan_scope.recent_searches[0] 
                               if self.config.scan_scope.recent_searches else "")
        search_layout.addWidget(self.search_edit)
        
        layout.addLayout(search_layout)
        
        # 搜索模板
        templates_layout = QHBoxLayout()
        templates_layout.addWidget(QLabel("搜索模板:"))
        
        self.search_template_combo = QComboBox()
        self.search_template_combo.addItem("选择模板...", "")
        for name, query in self.config.scan_scope.search_templates.items():
            self.search_template_combo.addItem(name.replace('_', ' ').title(), query)
        
        self.search_template_combo.currentIndexChanged.connect(self.on_template_selected)
        templates_layout.addWidget(self.search_template_combo)
        
        templates_layout.addStretch()
        layout.addLayout(templates_layout)
        
        self.setLayout(layout)
        
        # 更新UI状态
        self.update_ui_state()
        
        # 连接信号
        self.scope_group.buttonClicked.connect(self.update_ui_state)
    
    def update_ui_state(self):
        """更新UI状态"""
        # 获取当前选择的范围
        current_scope = self.get_scope_type()
        
        # 启用/禁用相关控件
        is_selected_decks = (current_scope == "selected_decks")
        is_custom_search = (current_scope == "custom_search")
        
        self.deck_select_button.setEnabled(is_selected_decks)
        self.deck_count_label.setEnabled(is_selected_decks)
        self.search_edit.setEnabled(is_custom_search)
        self.search_template_combo.setEnabled(is_custom_search)
        
        # 更新牌组计数标签
        if is_selected_decks:
            count = len(self.selected_decks)
            if count > 0:
                self.deck_count_label.setText(f"(已选择 {count} 个牌组)")
            else:
                self.deck_count_label.setText("(未选择)")
    
    def get_scope_type(self) -> str:
        """获取当前选择的范围类型"""
        button_id = self.scope_group.checkedId()
        
        if button_id == 0:
            return "all"
        elif button_id == 1:
            return "current_deck"
        elif button_id == 2:
            return "selected_decks"
        elif button_id == 3:
            return "selected_cards"
        elif button_id == 4:
            return "custom_search"
        else:
            return self.config.scan_scope.default_scope
    
    def select_decks(self):
        """选择牌组"""
        # 获取牌组列表
        deck_list = self.scanner.get_deck_list()
        
        if not deck_list:
            showWarning("无法获取牌组列表")
            return
        
        # 显示选择对话框
        dialog = DeckSelectionDialog(deck_list, self.selected_decks, self.include_subdecks, self)
        if dialog.exec():
            self.selected_decks = dialog.get_selected_decks()
            self.include_subdecks = dialog.include_subdecks_check.isChecked()
            self.update_ui_state()
    
    def on_template_selected(self, index):
        """搜索模板选择"""
        if index > 0:  # 跳过第一个"选择模板..."
            query = self.search_template_combo.currentData()
            self.search_edit.setText(query)
            self.custom_search_radio.setChecked(True)
            self.update_ui_state()
    

    def get_scan_scope(self) -> ScanScope:
        """获取扫描范围配置"""
        scope_type = self.get_scope_type()
        
        if scope_type == "all":
            return ScanScope(
                scope_type="all",
                include_subdecks=False  # 所有卡片不需要包含子牌组
            )
        
        elif scope_type == "current_deck":
            return ScanScope(
                scope_type="current_deck",
                include_subdecks=self.include_subdecks
            )
        
        elif scope_type == "selected_decks":
            return ScanScope(
                scope_type="selected_decks",
                deck_ids=list(self.selected_decks),
                include_subdecks=self.include_subdecks
            )
        
        elif scope_type == "selected_cards":
            # 从浏览器获取选中卡片
            card_ids = self.scanner.get_selected_cards_from_browser()
            return ScanScope(
                scope_type="selected_cards",
                card_ids=card_ids
            )
        
        elif scope_type == "custom_search":
            search_query = self.search_edit.text().strip()
            
            # 保存到最近搜索
            if search_query and search_query not in self.config.scan_scope.recent_searches:
                self.config.scan_scope.recent_searches.insert(0, search_query)
                if len(self.config.scan_scope.recent_searches) > self.config.scan_scope.max_history:
                    self.config.scan_scope.recent_searches.pop()
            
            return ScanScope(
                scope_type="custom_search",
                search_query=search_query
            )
        
        else:
            # 默认返回所有卡片
            return ScanScope(scope_type="all")
    
    def update_config(self):
        """更新配置"""
        scope_type = self.get_scope_type()
        self.config.scan_scope.default_scope = scope_type
        self.config.scan_scope.include_subdecks = self.include_subdecks


class ImageOrganizerDialog(QDialog):
    """图片整理对话框 - 优化版"""
    
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.scanner = plugin.scanner
        self.processor = plugin.processor
        self.config = plugin.config.current_config
        self.cards = []
        self.scanned = False
        self.scan_scope = None
        self.optimization_options = {}
        
        self.init_ui()
        
        # 能够自适应桌面大小
        screen = self.screen()
        if screen:
            geom = screen.availableGeometry()
            # 设为屏幕的 80%，但保证至少有 1000x600 的大小，同时不超过屏幕尺寸
            width = min(geom.width(), max(1000, int(geom.width() * 0.8)))
            height = min(geom.height(), max(600, int(geom.height() * 0.8)))
            self.resize(width, height)
            
            # 居中显示
            x = (geom.width() - width) // 2
            y = (geom.height() - height) // 2
            self.move(geom.x() + x, geom.y() + y)
        else:
            self.resize(1200, 600)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("Anki图片整理工具 - 专业版")
        
        # 创建主布局
        main_layout = QHBoxLayout()
        
        # 左侧面板（范围选择和统计）
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # 范围选择
        scope_group = QGroupBox("扫描范围")
        scope_layout = QVBoxLayout()
        
        self.scope_widget = ScanScopeWidget(self.config, self.scanner)
        scope_layout.addWidget(self.scope_widget)
        scope_group.setLayout(scope_layout)
        left_layout.addWidget(scope_group)
        
        # 扫描按钮
        scan_layout = QHBoxLayout()
        
        self.estimate_button = QPushButton("预估范围大小")
        self.estimate_button.clicked.connect(self.estimate_scope)
        scan_layout.addWidget(self.estimate_button)
        
        self.scan_button = QPushButton("开始扫描")
        self.scan_button.clicked.connect(self.scan_cards)
        scan_layout.addWidget(self.scan_button)
        
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        scan_layout.addWidget(self.scan_progress)
        
        left_layout.addLayout(scan_layout)
        
        # 统计信息
        self.stats_group = QGroupBox("扫描结果统计")
        stats_layout = QVBoxLayout()
        
        self.stats_label = QTextBrowser()
        self.stats_label.setOpenExternalLinks(True)
        self.stats_label.setHtml("等待扫描...")
        self.stats_label.setMinimumHeight(200)
        
        stats_layout.addWidget(self.stats_label)
        self.stats_group.setLayout(stats_layout)
        left_layout.addWidget(self.stats_group)
        
        # 牌组统计（使用滚动区域）
        deck_stats_group = QGroupBox("牌组统计")
        deck_stats_layout = QVBoxLayout()
        
        # 创建滚动区域
        deck_stats_scroll = QScrollArea()
        deck_stats_scroll.setWidgetResizable(True)
        deck_stats_scroll.setMinimumHeight(150)
        
        # 创建牌组统计容器
        deck_stats_container = QWidget()
        deck_stats_container_layout = QVBoxLayout()
        
        self.deck_stats_label = QLabel("")
        self.deck_stats_label.setWordWrap(True)
        self.deck_stats_label.setTextFormat(Qt.TextFormat.RichText)
        deck_stats_container_layout.addWidget(self.deck_stats_label)
        
        deck_stats_container.setLayout(deck_stats_container_layout)
        deck_stats_scroll.setWidget(deck_stats_container)
        
        deck_stats_layout.addWidget(deck_stats_scroll)
        deck_stats_group.setLayout(deck_stats_layout)
        deck_stats_group.setVisible(False)
        left_layout.addWidget(deck_stats_group)
        
        # 优化选项按钮
        self.optimize_button = QPushButton("图片优化选项...")
        self.optimize_button.clicked.connect(self.show_optimization_options)
        self.optimize_button.setEnabled(False)
        left_layout.addWidget(self.optimize_button)
        
        # 优化统计
        self.optimization_stats_label = QLabel("")
        self.optimization_stats_label.setWordWrap(True)
        self.optimization_stats_label.setVisible(False)
        left_layout.addWidget(self.optimization_stats_label)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        
        # 右侧面板（处理选项和结果）
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        # 处理选项区域
        options_group = QGroupBox("处理选项")
        options_layout = QVBoxLayout()
        row1_option_layout = QHBoxLayout()

        # 命名模式
        naming_layout = QVBoxLayout()
        naming_layout.addWidget(QLabel("命名模式:"))
        self.naming_combo = QComboBox()
        for key, value in self.config.naming_patterns.items():
            self.naming_combo.addItem(value, key)
        self.naming_combo.setCurrentText(
            self.config.naming_patterns.get(
                self.config.default_naming_pattern,
                "MD5哈希值"
            )
        )
        naming_layout.addWidget(self.naming_combo)
        row1_option_layout.addLayout(naming_layout)

        
        # 自定义命名模式
        self.custom_pattern_edit = QLineEdit(self.config.default_file_pattern)
        self.custom_pattern_edit.setPlaceholderText("例如: img_{hash}{ext}")
        self.custom_pattern_label = QLabel("自定义模式:")
        self.custom_pattern_label.setVisible(False)
        self.custom_pattern_edit.setVisible(False)
        
        # 优化策略
        strategy_layout = QVBoxLayout()
        strategy_layout.addWidget(QLabel("优化策略:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["最小优化", "平衡优化", "激进优化"])
        self.strategy_combo.setCurrentText({
            "minimal": "最小优化",
            "balanced": "平衡优化",
            "aggressive": "激进优化"
        }.get(self.config.optimization_strategy, "平衡优化"))
        strategy_layout.addWidget(self.strategy_combo)
        row1_option_layout.addLayout(strategy_layout)

        # 处理限制
        limit_layout = QVBoxLayout()
        limit_layout.addWidget(QLabel("最大处理卡片数:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100000)
        self.limit_spin.setValue(0)
        self.limit_spin.setSpecialValueText("无限制")
        limit_layout.addWidget(self.limit_spin)
        row1_option_layout.addLayout(limit_layout)

        options_layout.addLayout(row1_option_layout)

        row2_option_layout = QHBoxLayout()

        # 备份选项
        self.backup_checkbox = QCheckBox("处理前自动备份")
        self.backup_checkbox.setChecked(self.config.auto_backup)
        row2_option_layout.addWidget(self.backup_checkbox)
        
        # 试运行选项
        self.dry_run_checkbox = QCheckBox("试运行（不实际修改文件）")
        self.dry_run_checkbox.setChecked(True)
        row2_option_layout.addWidget(self.dry_run_checkbox)
        
        # 启用图片优化
        self.enable_optimization_check = QCheckBox("启用图片优化")
        self.enable_optimization_check.setChecked(True)
        self.enable_optimization_check.stateChanged.connect(
            self.on_optimization_changed
        )
        row2_option_layout.addWidget(self.enable_optimization_check)
        
        # 显示不符条件项
        self.show_unqualified_check = QCheckBox("显示不符条件项")
        self.show_unqualified_check.setChecked(False)
        self.show_unqualified_check.stateChanged.connect(self.on_show_unqualified_changed)
        row2_option_layout.addWidget(self.show_unqualified_check)

        row2_option_layout.addStretch()
        options_layout.addLayout(row2_option_layout)
        
        # 自定义命名模式行
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(self.custom_pattern_label)
        custom_layout.addWidget(self.custom_pattern_edit)
        custom_layout.addStretch()
        options_layout.addLayout(custom_layout)

        options_group.setLayout(options_layout)
        right_layout.addWidget(options_group)
        
        # 结果表格
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "卡片ID", "牌组", "原文件名", "原文件大小", "新文件名", "大小节省", "状态", "操作"
        ])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSortingEnabled(True)
        right_layout.addWidget(self.results_table)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.process_button = QPushButton("开始处理")
        self.process_button.clicked.connect(self.process_images)
        self.process_button.setEnabled(False)
        button_layout.addWidget(self.process_button)
        
        self.export_button = QPushButton("导出结果")
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        right_layout.addLayout(button_layout)
        right_panel.setLayout(right_layout)
        
        # 分割布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        
        # 连接信号
        self.naming_combo.currentIndexChanged.connect(self.on_naming_pattern_changed)
        
        # 检查选中卡片范围是否可用
        self.check_selected_cards_available()
    
    def check_selected_cards_available(self):
        """检查选中卡片范围是否可用"""
        card_ids = self.scanner.get_selected_cards_from_browser()
        if not card_ids:
            # 禁用选中卡片选项
            for btn in self.scope_widget.scope_group.buttons():
                if btn.text().startswith("选中卡片"):
                    btn.setEnabled(False)
                    btn.setToolTip("请在卡片浏览器中选择卡片后使用此功能")
    
    def on_naming_pattern_changed(self, index):
        """命名模式改变事件"""
        pattern = self.naming_combo.currentData()
        show_custom = (pattern == "custom")
        self.custom_pattern_label.setVisible(show_custom)
        self.custom_pattern_edit.setVisible(show_custom)
    
    def on_optimization_changed(self, state):
        """优化选项改变事件"""
        enabled = state == Qt.CheckState.Checked.value
        self.optimize_button.setEnabled(enabled)
    
    def show_optimization_options(self):
        """显示优化选项对话框"""
        dialog = OptimizationOptionsDialog(self.config, self)
        if dialog.exec():
            options = dialog.get_options()
            self.optimization_options = options
    
    def estimate_scope(self):
        """预估范围大小（后台线程）"""
        try:
            scope = self.scope_widget.get_scan_scope()
            self.estimate_button.setEnabled(False)
            self.stats_label.setHtml("⏱️ 正在预估范围大小，请稍候...")
            
            self.estimate_thread = EstimateThread(self.scanner, scope, self)
            self.estimate_thread.finished_signal.connect(self._on_estimate_finished)
            self.estimate_thread.error_signal.connect(self._on_estimate_error)
            self.estimate_thread.start()
            
        except Exception as e:
            self.estimate_button.setEnabled(True)
            showWarning(f"准备预估时出错: {str(e)}")

    def _on_estimate_finished(self, estimate):
        self.estimate_button.setEnabled(True)
        if estimate['card_count'] == 0:
            self.stats_label.setHtml("⚠️ 未找到符合条件的卡片")
            return
        
        estimate_text = (
            f"<b>预估范围大小:</b><br>"
            f"• 卡片数量: <b>{estimate['card_count']} 张</b><br>"
            f"• 预估图片数: <b>{estimate['estimated_images']} 个</b><br>"
            f"• 预估处理时间: <b>{estimate['estimated_time_minutes']} 分钟</b><br>"
            f"• 基于 {estimate['sample_size']} 张卡片的样本估算"
        )
        
        self.stats_label.setHtml(estimate_text)

    def _on_estimate_error(self, error_msg):
        self.estimate_button.setEnabled(True)
        self.stats_label.setHtml(f"预估失败: {error_msg}")
        showWarning(f"预估范围大小时出错: {error_msg}")

    def scan_cards(self):
        """扫描卡片"""
        # 更新配置
        self.scope_widget.update_config()
        
        # 获取扫描范围
        self.scan_scope = self.scope_widget.get_scan_scope()
        
        # 应用处理限制
        limit = self.limit_spin.value()
        if limit > 0:
            self.scan_scope.limit = limit
        
        # 检查范围有效性
        if self.scan_scope.scope_type == "selected_cards":
            card_ids = self.scanner.get_selected_cards_from_browser()
            if not card_ids:
                showWarning("未在卡片浏览器中找到选中的卡片。\n请先在卡片浏览器中选择卡片，然后重试。")
                return
            self.scan_scope.card_ids = card_ids
        
        elif self.scan_scope.scope_type == "custom_search":
            if not self.scan_scope.search_query:
                showWarning("请输入搜索条件")
                return
        
        # 检查PIL是否可用
        if not HAS_PIL and self.enable_optimization_check.isChecked():
            reply = QMessageBox.question(
                self,
                "缺少依赖",
                "PIL/Pillow库未安装，图片优化功能将不可用。\n是否现在安装？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.processor.install_pillow():
                    showInfo("Pillow安装成功，请重启插件。")
                else:
                    showWarning("Pillow安装失败，图片优化功能将不可用。")
                    self.enable_optimization_check.setChecked(False)
        
        # 开始扫描
        self.scan_button.setEnabled(False)
        self.scan_progress.setVisible(True)
        self.scan_progress.setRange(0, 0)  # 不确定模式
        
        # 异步扫描
        self.perform_scan()
    
    def perform_scan(self):
        """执行扫描（启动后台线程）"""
        self.stats_label.setHtml("⏱️ 正在扫描卡片并统信息，过程可能需要一些时间，请耐心等待...")
        self.scan_thread = ScanThread(self.scanner, self.scan_scope, self)
        self.scan_thread.finished_signal.connect(self._on_scan_finished)
        self.scan_thread.error_signal.connect(self._on_scan_error)
        self.scan_thread.start()
        
    def _on_scan_finished(self, cards, stats):
        self.scan_button.setEnabled(True)
        self.scan_progress.setVisible(False)
        self.cards = cards
        self.scanned = True
        
        # 格式化统计信息
        stats_text = self.format_stats_text(stats)
        
        if getattr(self, 'last_optimization_stats_html', None):
            if hasattr(self, 'stats_group'):
                self.stats_group.setTitle("优化结果统计")
            stats_text = self.last_optimization_stats_html + "<br><br><hr><br><b>（自动刷新）当前卡片最新扫描状态:</b><br>" + stats_text
            # 显示一次后清空，以备下次手动扫描还原
            self.last_optimization_stats_html = None
        else:
            if hasattr(self, 'stats_group'):
                self.stats_group.setTitle("扫描结果统计")
                
        self.stats_label.setHtml(stats_text)
        
        # 显示牌组统计
        if stats['deck_stats']:
            deck_text = self.format_deck_stats_text(stats['deck_stats'])
            self.deck_stats_label.setText(deck_text)
            
            # 显示牌组统计组
            deck_stats_group = self.findChild(QGroupBox, "牌组统计")
            if deck_stats_group:
                deck_stats_group.setVisible(True)
        
        # 更新表格（包含预估信息）
        self.update_results_table_with_estimates(stats)
        
        # 启用处理按钮
        has_images = len(self.cards) > 0
        self.process_button.setEnabled(has_images)
        self.export_button.setEnabled(has_images)
        self.optimize_button.setEnabled(has_images and self.enable_optimization_check.isChecked())
        
        # 显示提示
        if has_images:
            tooltip(f"扫描完成，找到 {stats['total_cards']} 张包含图片的卡片")
        else:
            tooltip("扫描完成，未找到包含图片的卡片")
            
    def _on_scan_error(self, error_msg):
        self.scan_button.setEnabled(True)
        self.scan_progress.setVisible(False)
        self.stats_label.setHtml(f"扫描失败: {error_msg}")
        showWarning(f"扫描时出错: {error_msg}")
    
    def format_stats_text(self, stats: Dict) -> str:
        """格式化统计信息文本"""
        scan_time = stats.get('scan_time_seconds', 0.0)
        time_text = f"{scan_time:.2f} 秒" if scan_time > 0 else "未知"
        
        text = (
            f"<b>📊 扫描完成！</b> (耗时: {time_text})<br>"
            f"<b>范围:</b> {self.scope_widget.get_scope_type()}<br>"
            f"<b>包含图片的卡片:</b> {stats['total_cards']} 张<br>"
            f"<b>图片引用总数:</b> {stats['total_images']} 个<br>"
            f"<b>本地文件数:</b> {stats['existing_images']} 个<br>"
            f"<b>缺失文件数:</b> {stats['missing_images']} 个<br>"
            f"<b>唯一文件数:</b> {stats['unique_files']} 个<br>"
            f"<b>总文件大小:</b> {stats['total_file_size_mb']} MB<br>"
            f"<b>预估节省空间:</b> {stats['total_estimated_savings_mb']} MB<br>"
            f"<b>预估压缩率:</b> {stats['estimated_compression_ratio']}%"
        )
        return text
    
    def format_deck_stats_text(self, deck_stats: Dict) -> str:
        """格式化牌组统计文本"""
        text = "<b>📈 按牌组统计:</b><br>"
        
        # 按文件大小排序
        sorted_decks = sorted(
            deck_stats.items(), 
            key=lambda x: x[1]['file_size'], 
            reverse=True
        )
        
        for deck_name, deck_stat in sorted_decks[:15]:  # 最多显示15个牌组
            size_mb = deck_stat['file_size'] / (1024 * 1024)
            savings_mb = deck_stat['estimated_savings'] / (1024 * 1024)
            
            text += (
                f"• <b>{deck_name}</b><br>"
                f"&nbsp;&nbsp;卡片: {deck_stat['card_count']}, "
                f"图片: {deck_stat['image_count']}, "
                f"大小: {size_mb:.1f} MB, "
                f"预估节省: {savings_mb:.1f} MB<br>"
            )
        
        if len(deck_stats) > 15:
            text += f"<br>... 还有 {len(deck_stats) - 15} 个牌组"
        
        return text
    
    def generate_estimated_filename(self, image_ref: ImageReference, 
                                   naming_pattern: str) -> str:
        """生成预估的新文件名"""
        if not image_ref.file_hash:
            return "待计算"
        
        # 获取文件扩展名
        try:
            path = Path(image_ref.original_path)
            ext = path.suffix.lower()
        except:
            ext = ".jpg"  # 默认扩展名
        
        if naming_pattern == "hash":
            # 使用哈希值前8位
            return f"img_{image_ref.file_hash}{ext}"
        
        elif naming_pattern == "timestamp":
            # 使用时间戳
            timestamp = int(time.time() * 1000)
            return f"img_{timestamp}{ext}"
        
        elif naming_pattern == "sequence":
            # 使用序列号（这里用卡片ID代替）
            return f"img_{image_ref.card_id:06d}{ext}"
        
        else:  # custom
            # 自定义模式
            file_hash = image_ref.file_hash or "unknown"
            return self.config.default_file_pattern.format(
                hash=file_hash[:8],
                timestamp=int(time.time()),
                sequence=image_ref.card_id,
                ext=ext
            )
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes <= 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} TB"
    
    def on_show_unqualified_changed(self, state):
        """显示不符条件项 状态改变"""
        if hasattr(self, 'scanned') and self.scanned:
            self.update_results_table_with_estimates(None)
            
    def update_results_table_with_estimates(self, stats: Dict = None):
        """更新结果表格（包含预估信息）"""
        self.results_table.setUpdatesEnabled(False)
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        
        show_unqualified = getattr(self, 'show_unqualified_check', None)
        show_unqualified = show_unqualified.isChecked() if show_unqualified else False
        min_size_bytes = self.config.compression.min_file_size_kb * 1024  # 当前配置的阈值
        
        # 收集图片引用（过滤不符条件的）
        all_image_refs = []
        for card in self.cards:
            for image_ref in card['images']:
                is_qualified = True
                if not image_ref.file_exists:
                    is_qualified = False
                elif min_size_bytes > 0 and image_ref.file_size < min_size_bytes:
                    is_qualified = False
                    
                if show_unqualified or is_qualified:
                    all_image_refs.append((card, image_ref))
                
        total_images = len(all_image_refs)
        MAX_ROWS = 1000
        
        # 超过限制时提取前500和后500
        if total_images > MAX_ROWS:
            display_refs = all_image_refs[:500] + all_image_refs[-500:]
        else:
            display_refs = all_image_refs
            
        display_count = len(display_refs)
        
        # 一次性分配行，避免增量分配带来的开销
        self.results_table.setRowCount(display_count)
        
        row = 0
        naming_pattern = self.naming_combo.currentData()
        
        for card, image_ref in display_refs:
            # 卡片ID
                card_id_item = QTableWidgetItem(str(image_ref.card_id))
                self.results_table.setItem(row, 0, card_id_item)
                
                # 牌组名称
                deck_item = QTableWidgetItem(card.get('deck_name', ''))
                self.results_table.setItem(row, 1, deck_item)
                
                # 原文件名
                path_item = QTableWidgetItem(image_ref.original_path)
                self.results_table.setItem(row, 2, path_item)

                # 原文件大小（新增列）
                size_text = self.format_size(image_ref.file_size)
                size_item = QTableWidgetItem(size_text)
                self.results_table.setItem(row, 3, size_item)

                # 新文件名（预估）
                estimated_filename = self.generate_estimated_filename(image_ref, naming_pattern)
                new_name_item = QTableWidgetItem(estimated_filename)
                new_name_item.setToolTip("基于当前命名模式的预估文件名")
                self.results_table.setItem(row, 4, new_name_item)
                
                # 大小节省（预估）
                if image_ref.estimated_savings > 0:
                    savings_text = self.format_size(image_ref.estimated_savings)
                    savings_item = QTableWidgetItem(f"~{savings_text}")
                    savings_item.setToolTip(f"预估节省空间: {savings_text}")
                    
                    # 根据节省大小设置颜色
                    if image_ref.estimated_savings > 1024 * 1024:  # 大于1MB
                        savings_item.setForeground(QColor(0, 128, 0))  # 绿色
                    elif image_ref.estimated_savings > 1024 * 100:  # 大于100KB
                        savings_item.setForeground(QColor(255, 140, 0))  # 橙色
                    
                    self.results_table.setItem(row, 5, savings_item)
                else:
                    savings_item = QTableWidgetItem("无")
                    savings_item.setToolTip("此文件类型可能无法进一步优化")
                    savings_item.setForeground(QColor(128, 128, 128))  # 灰色
                    self.results_table.setItem(row, 5, savings_item)
                
                # 状态
                if not image_ref.file_exists:
                    status = "❌ 缺失"
                    color = QColor(255, 0, 0)  # 红色
                elif min_size_bytes > 0 and image_ref.file_size < min_size_bytes:
                    # 文件大小小于阈值，将不会被处理
                    status = "⏭️ 小于阈值"
                    color = QColor(128, 128, 128)  # 灰色
                elif image_ref.file_size > 1024 * 1024 * 5:  # 大于5MB
                    status = "⚠️ 大文件"
                    color = QColor(255, 165, 0)  # 橙色
                else:
                    status = "✅ 正常"
                    color = QColor(0, 128, 0)  # 绿色
                
                status_item = QTableWidgetItem(status)
                status_item.setForeground(color)
                self.results_table.setItem(row, 6, status_item)
                
                # 操作（预览按钮）
                preview_btn = QPushButton("预览")
                preview_btn.clicked.connect(
                    lambda checked, path=image_ref.original_path: self.preview_image(path)
                )
                preview_btn.setEnabled(image_ref.file_exists)
                self.results_table.setCellWidget(row, 7, preview_btn)
                
                row += 1
        
        # 恢复表格更新和排序
        self.results_table.setUpdatesEnabled(True)
        self.results_table.setSortingEnabled(True)
        
        # 视情况调整列宽，如果超过最大行数会有明显卡死，干脆不在大容量时全表 resize
        if total_images <= 500:
            self.results_table.resizeColumnsToContents()
            
        # 超出截断提示
        if total_images > MAX_ROWS:
            current_html = self.stats_label.toHtml()
            trunc_msg = f"<br><br><b style='color:orange;'>⚠️ 提示：为了防止界面卡死，上方结果表格仅展示了前 500 张和后 500 张（共 {MAX_ROWS} 张）图片。处理和导出操作依然会自动应用到全部 {total_images} 张图片。</b>"
            self.stats_label.setHtml(current_html + trunc_msg)
    
    def preview_image(self, image_path: str):
        """预览图片"""
        from pathlib import Path
        
        try:
            # 尝试打开图片文件
            file_path = Path(image_path)
            if not file_path.exists():
                # 尝试在媒体目录中查找
                media_dir = self.processor.media_dir
                file_path = media_dir / file_path.name
            
            if file_path.exists():
                import os
                import sys
                # 使用系统默认程序打开
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                elif os.name == 'posix':  # macOS, Linux
                    import subprocess
                    subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', str(file_path)])
        except Exception as e:
            showWarning(f"无法预览图片: {str(e)}")
    
    def process_images(self):
        """处理图片"""
        if not self.scanned:
            showWarning("请先扫描卡片")
            return
        
        if not self.cards:
            showInfo("没有找到需要处理的图片")
            return
        
        # 确认
        if not self.dry_run_checkbox.isChecked():
            message = "确定要处理图片吗？此操作将：\n"
            message += f"• 处理范围: {self.scope_widget.get_scope_type()}\n"
            message += f"• 卡片数量: {len(self.cards)} 张\n"

            # 收集要处理的文件数量
            files_to_process = set()
            for card in self.cards:
                for image_ref in card['images']:
                    if image_ref.file_exists:
                        original_path = self.processor._find_image_file(image_ref.original_path)
                        if original_path and original_path.exists():
                            files_to_process.add(original_path)
            message += f"• 待处理文件: {len(files_to_process)} 个\n"

            if self.enable_optimization_check.isChecked():
                message += "• 转换图片格式为JPG\n"
                message += "• 调整图片分辨率\n"
                message += "• 压缩图片以节省空间\n"

            if self.backup_checkbox.isChecked():
                message += "• 自动备份待处理文件\n"
                
            message += "\n此操作不可逆。建议先试运行。"
            
            if not askUser(message):
                return
        
        # 获取选项
        naming_pattern = self.naming_combo.currentData()
        optimize_images = self.enable_optimization_check.isChecked()
        
        # 分辨率预设
        resolution_preset = None
        if optimize_images and self.optimization_options:
            resolution_preset = self.optimization_options.get('resolution_preset')

        # 临时更新配置中的 auto_backup 设置
        original_auto_backup = self.config.auto_backup
        self.config.auto_backup = self.backup_checkbox.isChecked()

        # 处理， 备份逻辑在process_images中
        try:
            processed, errors = self.plugin.process_images(
                self.cards,
                naming_pattern,
                self.dry_run_checkbox.isChecked(),
                optimize_images,
                resolution_preset
            )
            
            # 显示结果
            result_text = f"<b>处理（优化）完成！</b><br>成功处理: {len(processed)} 个文件<br>错误: {len(errors)} 个"
            
            # 显示优化统计
            if optimize_images:
                stats = self.processor.get_optimization_stats()
                optimization_text = (
                    f"<br><br><b>最后一次优化专项统计:</b> (耗时: {stats.get('processing_time_seconds', 0.0):.2f} 秒)<br>"
                    f"• 格式转换: <b>{stats['format_converted']}</b> 个<br>"
                    f"• 分辨率调整: <b>{stats['resized']}</b> 个<br>"
                    f"• 跳过（小于阈值）: <b>{stats.get('skipped_size', 0)}</b> 个<br>"
                    f"• 帮您节省空间: <b style='color:green;'>{stats['size_reduction_mb']:.2f} MB</b><br>"
                    f"• 平均压缩率: <b>{stats['compression_ratio']:.2%}</b>"
                )
                result_text += optimization_text
                
                # 隐藏原先独立的优化结果小标签，因为现在我们要合并到大框里去
                self.optimization_stats_label.setVisible(False)
            
            if errors:
                error_details = "<br>".join(
                    [f"卡片 {e['card_id']}: {e['error']}" 
                     for e in errors[:10]]
                )
                if len(errors) > 10:
                    error_details += f"<br>...还有 {len(errors) - 10} 个错误"
                
                result_text += f"<br><br><b style='color:red;'>部分错误详情:</b><br>{error_details}"
                showWarning(f"处理已完成，但期间遇到少量错误！")
            else:
                showInfo("所有选择的图片均已处理并优化完成！您节省了宝贵的空间。")
            
            # 记录本次优化结果文本，留待下方的自动扫描完成后与其合并显示
            self.last_optimization_stats_html = result_text
            
            # 重新扫描以更新状态
            self.scan_cards()
            
        except Exception as e:
            showWarning(f"处理时出错: {str(e)}")
        finally:
            # 恢复原始的 auto_backup 设置
            self.config.auto_backup = original_auto_backup

    def export_results(self):
        """导出结果"""
        if not self.cards:
            return
        
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出结果",
            str(Path.home() / "anki_image_export.csv"),
            "CSV文件 (*.csv);;JSON文件 (*.json)"
        )
        
        if file_name:
            try:
                ext = Path(file_name).suffix.lower()
                
                if ext == '.json':
                    # 导出为JSON
                    import json
                    export_data = {
                        'scan_scope': self.scan_scope.__dict__ if self.scan_scope else {},
                        'cards_count': len(self.cards),
                        'cards': self.cards[:1000]  # 限制导出数量
                    }
                    
                    with open(file_name, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                else:
                    # 导出为CSV
                    with open(file_name, 'w', encoding='utf-8') as f:
                        # 写入表头
                        f.write("卡片ID,牌组,原文件名,原文件大小,新文件名,大小节省,状态\n")

                        # 写入数据
                        for row in range(self.results_table.rowCount()):
                            items = []
                            for col in range(self.results_table.columnCount()):
                                if col == 7:  # 跳过操作列
                                    continue
                                item = self.results_table.item(row, col)
                                if item:
                                    items.append(item.text())
                                else:
                                    items.append("")
                            f.write(','.join(items) + '\n')
                
                showInfo(f"结果已导出到: {file_name}")
                
            except Exception as e:
                showWarning(f"导出时出错: {str(e)}")