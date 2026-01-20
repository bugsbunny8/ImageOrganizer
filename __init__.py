"""
Anki图片整理插件 - 专业版
支持范围选择和图片优化
"""

import os
import sys

# 检查PIL/Pillow
try:
    # 1. 获取本插件所在的目录路径
    ADDON_DIR = os.path.dirname(__file__)
    # 2. 将插件下的lib目录添加到模块搜索路径的最前面
    LIB_DIR = os.path.join(ADDON_DIR, 'lib')
    sys.path.insert(0, LIB_DIR)

    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: PIL/Pillow未安装，图片优化功能将受限")

import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re

from anki import hooks
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, showWarning, askUser, tooltip

from .config import Config
from .scanner import CardScanner, ScanScope
from .processor import ImageProcessor
from .ui import ImageOrganizerDialog
from .settings_dialog import SettingsDialog

# 插件配置
ADDON_NAME = "Image Organizer Pro"
VERSION = "3.0.0"

class ImageOrganizer:
    """图片整理插件主类 - 专业版"""
    
    def __init__(self):
        self.config = Config()
        self.scanner = CardScanner()
        self.processor = ImageProcessor(self.config)
        self.has_pil = HAS_PIL
        self.setup_menu()
        
        # 显示PIL状态
        if not HAS_PIL:
            print(f"{ADDON_NAME}: PIL/Pillow未安装，图片优化功能将不可用")
            print("请使用命令安装: pip install Pillow")
    
    def setup_menu(self):
        """创建菜单项"""
        menu = QMenu(ADDON_NAME, mw)
        
        # 主功能
        organize_action = QAction("整理图片...", mw)
        organize_action.triggered.connect(self.show_dialog)
        menu.addAction(organize_action)
        
        # 快速操作子菜单
        quick_menu = QMenu("快速处理", mw)
        
        # 当前牌组
        current_deck_action = QAction("处理当前牌组", mw)
        current_deck_action.triggered.connect(lambda: self.quick_process("current_deck"))
        quick_menu.addAction(current_deck_action)
        
        # 选中卡片
        selected_cards_action = QAction("处理选中卡片", mw)
        selected_cards_action.triggered.connect(lambda: self.quick_process("selected_cards"))
        quick_menu.addAction(selected_cards_action)
        
        # 所有卡片
        all_cards_action = QAction("处理所有卡片", mw)
        all_cards_action.triggered.connect(lambda: self.quick_process("all"))
        quick_menu.addAction(all_cards_action)
        
        menu.addMenu(quick_menu)
        
        # 安装依赖菜单
        if not HAS_PIL:
            menu.addSeparator()
            install_action = QAction("安装Pillow依赖...", mw)
            install_action.triggered.connect(self.install_pillow)
            menu.addAction(install_action)
        
        menu.addSeparator()
        
        # 设置
        settings_action = QAction("设置...", mw)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        
        mw.form.menuTools.addMenu(menu)
    
    def install_pillow(self):
        """安装Pillow库"""
        import subprocess
        
        reply = askUser(
            "此操作将尝试安装Pillow库以启用图片优化功能。\n"
            "需要管理员权限，确定要继续吗？"
        )
        
        if reply:
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", "Pillow"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    showInfo("Pillow安装成功！请重启Anki以启用图片优化功能。")
                else:
                    showWarning(f"安装失败:\n{stderr}")
                    
            except Exception as e:
                showWarning(f"安装过程中出错: {str(e)}")
    
    def quick_process(self, scope_type: str):
        """快速处理"""
        try:
            # 创建扫描范围
            if scope_type == "current_deck":
                scope = ScanScope(
                    scope_type="current_deck",
                    include_subdecks=self.config.current_config.scan_scope.include_subdecks
                )
                scope_name = "当前牌组"
                
            elif scope_type == "selected_cards":
                card_ids = self.scanner.get_selected_cards_from_browser()
                if not card_ids:
                    showWarning("未在卡片浏览器中找到选中的卡片。\n请先在卡片浏览器中选择卡片。")
                    return
                
                scope = ScanScope(
                    scope_type="selected_cards",
                    card_ids=card_ids
                )
                scope_name = "选中卡片"
                
            else:  # all
                scope = ScanScope(scope_type="all")
                scope_name = "所有卡片"
            
            # 扫描卡片
            cards = self.scanner.scan_scope(scope)
            
            if not cards:
                showInfo(f"在{scope_name}中未找到包含图片的卡片")
                return
            
            # 确认处理
            message = f"确定要处理{scope_name}中的图片吗？\n"
            message += f"找到 {len(cards)} 张包含图片的卡片\n\n"
            message += "此操作将：\n"
            message += "1. 重命名图片文件\n"
            message += "2. 转换为JPG格式（如适用）\n"
            message += "3. 调整到笔记本优化分辨率\n"
            message += "4. 压缩图片以节省空间\n\n"
            message += "建议先使用完整版插件进行试运行。"
            
            if not askUser(message):
                return
            
            # 处理图片
            processed, errors = self.processor.process_images(
                cards,
                naming_pattern=self.config.current_config.default_naming_pattern,
                dry_run=False,
                optimize_images=True,
                resolution_preset="laptop"
            )
            
            # 显示结果
            if errors:
                showWarning(f"处理完成！\n成功: {len(processed)} 个\n错误: {len(errors)} 个")
            else:
                showInfo(f"处理完成！成功处理 {len(processed)} 个图片文件")
                
        except Exception as e:
            showWarning(f"快速处理时出错: {str(e)}")
    
    def show_dialog(self):
        """显示主对话框"""
        dialog = ImageOrganizerDialog(self, mw)
        dialog.exec()
    
    def show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.config.current_config, mw)
        if dialog.exec():
            # 保存设置
            self.config.save_config()
    
    def scan_cards_with_scope(self, scope: ScanScope) -> List[Dict]:
        """使用指定范围扫描卡片"""
        return self.scanner.scan_scope(scope)
    
    def get_statistics(self) -> Dict:
        """获取统计信息（兼容旧版）"""
        cards = self.scanner.scan_all_cards()
        stats = self.scanner.get_statistics(cards)
        return stats
    
    def process_images(self, cards: List[Dict], 
                      naming_pattern: str = "hash",
                      dry_run: bool = False,
                      optimize_images: bool = True,
                      resolution_preset: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        处理图片重命名和优化
        
        Args:
            cards: 卡片列表
            naming_pattern: 命名模式
            dry_run: 试运行模式
            optimize_images: 是否优化图片
            resolution_preset: 分辨率预设名称
        
        Returns:
            (processed_items, errors)
        """
        return self.processor.process_images(
            cards, naming_pattern, dry_run, optimize_images, resolution_preset
        )
    
    def get_optimization_stats(self) -> Dict:
        """获取优化统计信息"""
        if hasattr(self.processor, 'get_optimization_stats'):
            return self.processor.get_optimization_stats()
        return {}
    
    def backup_media(self) -> str:
        """备份媒体文件夹（保持向后兼容，但建议使用新的备份逻辑）"""
        # 获取所有待处理的文件
        files_to_backup = set()
        
        # 如果有扫描结果，只备份待处理的文件
        if hasattr(self, 'cards') and self.cards:
            for card in self.cards:
                for image_ref in card['images']:
                    if image_ref.file_exists:
                        original_path = self.processor._find_image_file(image_ref.original_path)
                        if original_path and original_path.exists():
                            files_to_backup.add(original_path)
        
        if files_to_backup:
            # 使用新的备份方法
            backup_path = self.processor.backup_files(files_to_backup)
        else:
            # 如果没有特定文件，备份整个文件夹
            backup_path = self.processor.backup_media_folder()
        
        return backup_path
    
    def restore_backup(self, backup_path: str) -> bool:
        """从备份恢复"""
        return self.processor.restore_backup(backup_path)

# 初始化插件
img_organizer = None

def init_addon():
    """初始化插件"""
    global img_organizer
    img_organizer = ImageOrganizer()

# Anki加载插件时执行
hooks.addHook("profileLoaded", init_addon)

# 添加浏览器上下文菜单
def setup_browser_menu(browser):
    """设置浏览器上下文菜单"""
    from aqt.qt import QAction
    from aqt.utils import showWarning
    
    menu = browser.form.menuEdit
    if menu:
        # 添加分隔符
        menu.addSeparator()
        
        # 添加处理选中卡片菜单项
        def process_selected():
            if img_organizer:
                # 获取选中卡片
                card_ids = browser.selectedCards()
                
                if not card_ids:
                    showWarning("请先在卡片浏览器中选择卡片")
                    return
                
                # 扫描选中卡片
                cards = img_organizer.scanner.scan_selected_cards(card_ids)
                
                if not cards:
                    showWarning("选中的卡片中没有包含图片的卡片")
                    return
                
                # 显示处理对话框
                dialog = ImageOrganizerDialog(img_organizer, browser)
                
                # 设置范围为选中卡片
                from .ui import ScanScopeWidget
                dialog.scope_widget.selected_cards_radio.setChecked(True)
                dialog.scope_widget.update_ui_state()
                
                # 预扫描
                dialog.cards = cards
                dialog.scanned = True
                
                # 更新统计
                stats = img_organizer.scanner.get_statistics(cards)
                dialog.stats_label.setText(
                    f"选中的卡片: {len(card_ids)} 张\n"
                    f"包含图片的卡片: {stats['total_cards']} 张\n"
                    f"图片总数: {stats['total_images']} 个"
                )
                
                # 更新表格
                dialog.update_results_table()
                
                # 启用处理按钮
                dialog.process_button.setEnabled(True)
                dialog.export_button.setEnabled(True)
                
                dialog.exec()
        
        action = QAction("处理选中卡片的图片", browser)
        action.triggered.connect(process_selected)
        menu.addAction(action)

# 注册浏览器菜单
try:
    from aqt import gui_hooks
    gui_hooks.browser_menus_did_init.append(setup_browser_menu)
except ImportError:
    # 旧版Anki兼容
    pass