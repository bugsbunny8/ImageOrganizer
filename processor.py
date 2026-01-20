"""
图片处理器 - 增强版
支持格式转换和分辨率调整
"""
import os
import sys

import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Set
from datetime import datetime
import time
import subprocess
import sys

from .config import PluginConfig, Config
from .scanner import ImageReference, CardScanner, ScanScope

try:
    from PIL import Image, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: PIL/Pillow未安装，部分图片处理功能将不可用")

class ImageOptimizer:
    """图片优化器"""
    
    def __init__(self, config: PluginConfig):
        self.config = config
        self.has_pil = HAS_PIL
        self.supported_formats = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'gif']
        
        # 格式转换映射
        self.format_mapping = {
            'png': 'jpg',
            'bmp': 'jpg',
            'tiff': 'jpg',
            'tif': 'jpg',
            'webp': 'jpg',
            'heic': 'jpg',
            'heif': 'jpg'
        }
    
    def optimize_image(self, image_path: Path, 
                      target_format: str = None,
                      quality: int = None,
                      resolution: Tuple[int, int] = None) -> Tuple[Path, float]:
        """
        优化图片
        Returns:
            (优化后的文件路径, 压缩率)
        """
        if not self.has_pil:
            print("PIL system error")
            return image_path, 1.0
        
        try:
            # 获取原始文件大小
            original_size = image_path.stat().st_size
            
            # 打开图片
            with Image.open(image_path) as img:
                # 转换格式
                img = self._convert_image(img, target_format)
                
                # 调整分辨率
                if resolution and resolution != (0, 0):
                    img = self._resize_image(img, resolution)
                
                # 确定输出格式
                output_format = target_format or self._get_best_format(img.format)
                if output_format.lower() in ['jpg', 'jpeg']:
                    # JPG格式需要转换为RGB
                    if img.mode in ('RGBA', 'LA', 'P'):
                        print("convert in RGBA mode")
                        # 创建白色背景
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                
                # 生成临时文件名
                temp_path = image_path.parent / f"temp_{image_path.name}"
                
                # 保存优化后的图片
                save_kwargs = self._get_save_kwargs(output_format, quality)
                img.save(temp_path, **save_kwargs)
                
                # 检查压缩效果
                optimized_size = temp_path.stat().st_size
                compression_ratio = optimized_size / original_size
                
                # 只有当压缩有效时才使用新文件
                if compression_ratio < self.config.compression.min_compression_ratio:
                    return temp_path, compression_ratio
                else:
                    # 压缩无效，删除临时文件
                    temp_path.unlink(missing_ok=True)
                    return image_path, 1.0
                    
        except Exception as e:
            print(f"优化图片失败 {image_path}: {e}")
            return image_path, 1.0
    
    def _convert_image(self, img: Image.Image, target_format: str = None) -> Image.Image:
        """转换图片格式"""
        if not target_format:
            return img
        
        # 检查是否需要转换
        current_format = img.format.lower() if img.format else ''
        if current_format and current_format != target_format.lower():
            # 格式转换逻辑已在保存时处理
            pass
        
        return img
    
    def _resize_image(self, img: Image.Image, resolution: Tuple[int, int]) -> Image.Image:
        """调整图片分辨率"""
        if resolution == (0, 0):
            return img
        
        width, height = resolution
        config = self.config.resolution
        
        # 获取当前尺寸
        current_width, current_height = img.size
        
        # 如果已经小于目标尺寸，不放大
        if config.keep_aspect_ratio:
            if current_width <= width and current_height <= height:
                return img
            
            # 计算等比例缩放
            width_ratio = width / current_width
            height_ratio = height / current_height
            
            if config.resize_mode == "contain":
                # 保持宽高比，完全包含在目标尺寸内
                ratio = min(width_ratio, height_ratio)
            elif config.resize_mode == "cover":
                # 保持宽高比，覆盖整个目标区域
                ratio = max(width_ratio, height_ratio)
            else:  # fill
                # 填充目标区域，可能变形
                return img.resize((width, height), Image.Resampling.LANCZOS)
            
            new_width = int(current_width * ratio)
            new_height = int(current_height * ratio)
            
            # 确保不超过最大限制
            if config.max_width > 0 and new_width > config.max_width:
                ratio = config.max_width / new_width
                new_width = config.max_width
                new_height = int(new_height * ratio)
            
            if config.max_height > 0 and new_height > config.max_height:
                ratio = config.max_height / new_height
                new_height = config.max_height
                new_width = int(new_width * ratio)
            
            # 执行缩放
            return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        else:
            # 不保持宽高比
            new_width = min(width, config.max_width) if config.max_width > 0 else width
            new_height = min(height, config.max_height) if config.max_height > 0 else height
            return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _get_best_format(self, current_format: str) -> str:
        """获取最佳输出格式"""
        if not current_format:
            return self.config.target_format
        
        current_lower = current_format.lower()
        
        # 检查是否在可转换格式列表中
        if current_lower in self.config.convertible_formats:
            return self.config.target_format
        else:
            # 保持原格式
            return current_format if current_format in self.supported_formats else 'jpg'
    
    def _get_save_kwargs(self, format: str, quality: int = None) -> Dict:
        """获取保存参数"""
        kwargs = {
            'optimize': True,
            'quality': quality or self.config.compression.jpg_quality
        }
        
        if format.lower() == 'png':
            # PNG压缩设置
            kwargs.update({
                'compress_level': 9,
                'optimize': True
            })
        elif format.lower() == 'webp':
            # WebP设置
            kwargs.update({
                'method': 6,  # 0-6，越高压缩越好但越慢
                'quality': kwargs['quality']
            })
        
        # 是否保留元数据
        if not self.config.preserve_metadata:
            kwargs['exif'] = b''  # 清空EXIF
        
        return kwargs
    
    def can_optimize(self, image_path: Path) -> bool:
        """检查是否可以优化"""
        if not self.has_pil:
            return False
        
        ext = image_path.suffix.lower()
        return ext[1:] in self.config.convertible_formats or ext in ['.png', '.bmp', '.tiff', '.tif']


class ImageProcessor:
    """图片处理器 - 增强版"""
    
    def __init__(self, config: Union[PluginConfig, Config]):
        # 确保我们使用的是 PluginConfig 对象
        if hasattr(config, 'current_config'):
            # 如果是 Config 对象，获取内部的 PluginConfig
            self.config = config.get_config()
        else:
            # 已经是 PluginConfig 对象
            self.config = config
        
        self.scanner = CardScanner()
        self.media_dir = self.scanner.get_media_directory()
        self.backup_dir = None
        self.optimizer = ImageOptimizer(self.config) if HAS_PIL else None
        
        # 处理统计
        self.stats = {
            'total_processed': 0,
            'format_converted': 0,
            'resized': 0,
            'size_reduction': 0,  # 字节
            'original_total_size': 0,
            'optimized_total_size': 0
        }
    
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
        processed = []
        errors = []
        
        # 重置统计
        self._reset_stats()
        
        # 获取分辨率设置
        if optimize_images and resolution_preset:
            resolution = self.config.get_resolution_preset(resolution_preset)
        else:
            resolution = (0, 0)
        
        # 生成文件名映射
        filename_map = self.generate_filename_map(cards, naming_pattern)
        
        # 收集所有待处理的文件路径（去重）
        files_to_backup = set()
        if not dry_run and self.config.auto_backup:
            for card in cards:
                for image_ref in card['images']:
                    if image_ref.file_exists:
                        original_path = self._find_image_file(image_ref.original_path)
                        if original_path and original_path.exists():
                            files_to_backup.add(original_path)
        
        # 备份文件（如果需要）
        backup_path = None
        if files_to_backup and not dry_run and self.config.auto_backup:
            backup_path = self.backup_files(files_to_backup)
            if backup_path:
                print(f"已备份 {len(files_to_backup)} 个文件到: {backup_path}")

        # 处理每个文件        
        for card in cards:
            for image_ref in card['images']:
                try:
                    if not image_ref.file_exists:
                        errors.append({
                            'card_id': image_ref.card_id,
                            'path': image_ref.original_path,
                            'error': '文件不存在'
                        })
                        continue
                    
                    original_path = self._find_image_file(image_ref.original_path)
                    if not original_path:
                        errors.append({
                            'card_id': image_ref.card_id,
                            'path': image_ref.original_path,
                            'error': '无法找到文件'
                        })
                        continue
                    
                    # 更新统计
                    original_size = original_path.stat().st_size
                    self.stats['original_total_size'] += original_size
                    self.stats['total_processed'] += 1
                    
                    # 优化图片
                    optimized_path = original_path
                    if optimize_images and self.optimizer:
                        # 检查是否需要优化
                        if self.optimizer.can_optimize(original_path):
                            optimized_path, compression_ratio = self.optimizer.optimize_image(
                                original_path,
                                target_format=self.config.target_format,
                                quality=self.config.compression.jpg_quality,
                                resolution=resolution
                            )
                            
                            if optimized_path != original_path:
                                self.stats['format_converted'] += 1
                                if resolution != (0, 0):
                                    self.stats['resized'] += 1
                                
                                # 更新大小统计
                                optimized_size = optimized_path.stat().st_size
                                size_reduction = original_size - optimized_size
                                if size_reduction > 0:
                                    self.stats['size_reduction'] += size_reduction
                                    self.stats['optimized_total_size'] += optimized_size
                    
                    # 生成新文件名
                    new_filename = self.generate_new_filename(
                        optimized_path, naming_pattern, filename_map
                    )

                    # 构建新路径
                    new_path = self.media_dir / new_filename
                    
                    # 检查是否已存在相同文件
                    if self.is_duplicate_file(optimized_path, new_path):
                        # 文件内容相同，只需更新引用
                        processed.append({
                            'card_id': image_ref.card_id,
                            'original': str(original_path),
                            'new': new_filename,
                            'action': 'reference_updated',
                            'size_reduction': original_size - optimized_path.stat().st_size,
                            'optimized': optimized_path != original_path
                        })
                        
                        # 清理临时文件
                        if optimized_path != original_path:
                            if not dry_run and optimized_path.name.startswith('temp_'):
                                optimized_path.unlink(missing_ok=True)
                    else:
                        # 需要移动文件
                        if not dry_run:
                            success = self.rename_file(optimized_path, new_path)
                            if not success:
                                errors.append({
                                    'card_id': image_ref.card_id,
                                    'path': str(original_path),
                                    'error': '移动文件失败'
                                })
                                continue
                        
                        processed.append({
                            'card_id': image_ref.card_id,
                            'original': str(original_path),
                            'new': str(new_path),
                            'action': 'file_optimized_and_renamed',
                            'size_reduction': original_size - optimized_path.stat().st_size,
                            'optimized': optimized_path != original_path
                        })
                    
                    # 更新卡片引用
                    if not dry_run:
                        self.update_card_reference(card, image_ref, new_filename)
                    
                except Exception as e:
                    errors.append({
                        'card_id': image_ref.card_id,
                        'path': image_ref.original_path,
                        'error': str(e)
                    })
        
        return processed, errors
    
    def _reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_processed': 0,
            'format_converted': 0,
            'resized': 0,
            'size_reduction': 0,
            'original_total_size': 0,
            'optimized_total_size': 0
        }
    
    def _find_image_file(self, path_str: str) -> Optional[Path]:
        """查找图片文件"""
        original_path = Path(path_str)
        
        # 检查完整路径
        if original_path.exists() and original_path.is_file():
            return original_path
        
        # 检查媒体目录
        media_path = self.media_dir / original_path.name
        if media_path.exists() and media_path.is_file():
            return media_path
        
        # 尝试去掉查询参数
        clean_name = original_path.name.split('?')[0]
        media_path = self.media_dir / clean_name
        if media_path.exists() and media_path.is_file():
            return media_path
        
        return None
    
    def generate_filename_map(self, cards: List[Dict], 
                            naming_pattern: str) -> Dict[str, str]:
        """生成文件名映射表"""
        filename_map = {}
        file_hashes = {}
        
        for card in cards:
            for image_ref in card['images']:
                if not image_ref.file_exists:
                    continue
                
                try:
                    file_path = self._find_image_file(image_ref.original_path)
                    if not file_path or not file_path.exists():
                        continue
                    
                    # 计算文件哈希
                    file_hash = self.calculate_file_hash(file_path)
                    
                    if file_hash in file_hashes:
                        # 文件已存在，使用相同的文件名
                        filename_map[str(file_path)] = file_hashes[file_hash]
                    else:
                        # 生成新文件名
                        ext = self._get_target_extension(file_path)
                        new_name = self.generate_filename(
                            file_path, naming_pattern, len(file_hashes), ext
                        )
                        filename_map[str(file_path)] = new_name
                        file_hashes[file_hash] = new_name
                
                except Exception as e:
                    print(f"生成文件名映射时出错: {e}")
        
        return filename_map
    
    def _get_target_extension(self, file_path: Path) -> str:
        """获取目标扩展名"""
        if not self.optimizer:
            return file_path.suffix.lower()
        
        # 检查是否需要转换格式
        if self.optimizer.can_optimize(file_path):
            return f".{self.config.target_format}"
        else:
            return file_path.suffix.lower()
    
    def generate_filename(self, file_path: Path, 
                         pattern: str, sequence: int, ext: str = None) -> str:
        """根据模式生成文件名"""
        if ext is None:
            ext = file_path.suffix.lower()
        
        if pattern == "hash":
            file_hash = self.calculate_file_hash(file_path)
            return f"img_{file_hash}{ext}"
        
        elif pattern == "timestamp":
            timestamp = int(time.time() * 1000)
            return f"img_{timestamp}_{sequence:04d}{ext}"
        
        elif pattern == "sequence":
            return f"img_{sequence:06d}{ext}"
        
        else:  # custom
            file_hash = self.calculate_file_hash(file_path)
            return self.config.default_file_pattern.format(
                hash=file_hash[:8],
                timestamp=int(time.time()),
                sequence=sequence,
                ext=ext
            )
    
    def generate_new_filename(self, file_path: Path, 
                            pattern: str, 
                            filename_map: Dict[str, str]) -> str:
        """生成新文件名"""
        if str(file_path) in filename_map:
            return filename_map[str(file_path)]
        
        # 生成新文件名
        return self.generate_filename(file_path, pattern, 0)
    
    def calculate_file_hash(self, file_path: Path, 
                           algorithm: str = "md5") -> str:
        """计算文件哈希值"""
        hash_func = hashlib.new(algorithm)
        
        try:
            with open(file_path, 'rb') as f:
                # 分块读取大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
        except Exception as e:
            print(f"计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def is_duplicate_file(self, file1: Path, file2: Path) -> bool:
        """检查两个文件是否相同"""
        if not file1.exists() or not file2.exists():
            return False
        
        if file1 == file2:
            return True
        
        # 比较文件大小
        if file1.stat().st_size != file2.stat().st_size:
            return False
        
        # 比较哈希值
        hash1 = self.calculate_file_hash(file1)
        hash2 = self.calculate_file_hash(file2)
        
        return hash1 == hash2
    
    def rename_file(self, source: Path, destination: Path) -> bool:
        """重命名/移动文件"""
        try:
            # 确保目标目录存在
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果目标文件已存在且相同，则跳过
            if destination.exists():
                if self.is_duplicate_file(source, destination):
                    return True
                else:
                    # 生成唯一文件名
                    counter = 1
                    while destination.exists():
                        new_name = f"{destination.stem}_{counter}{destination.suffix}"
                        destination = destination.parent / new_name
                        counter += 1
            
            # 移动文件
            shutil.move(str(source), str(destination))
            return True
            
        except Exception as e:
            print(f"重命名文件时出错: {e}")
            return False
    
    def update_card_reference(self, card: Dict, 
                            image_ref: ImageReference, 
                            new_filename: str) -> bool:
        """更新卡片中的图片引用"""
        from aqt import mw
        
        try:
            # 获取卡片
            anki_card = mw.col.get_card(image_ref.card_id)
            note = anki_card.note()
            
            # 查找字段
            field_content = note.fields[image_ref.field_index]  # 使用图像对应的正确字段
            
            # 替换图片引用
            old_path = image_ref.original_path
            new_path = new_filename
            
            # 使用正则表达式替换
            import re
            patterns = [
                f'src="{re.escape(old_path)}"',
                f"src='{re.escape(old_path)}'",
                f'src="{re.escape(old_path.split("?")[0])}"',
            ]
            
            updated = False
            for pattern in patterns:
                if re.search(pattern, field_content):
                    field_content = re.sub(
                        pattern, 
                        f'src="{new_path}"', 
                        field_content
                    )
                    updated = True
            
            if updated:
                note.fields[image_ref.field_index] = field_content
                note.flush()
                mw.col.update_note(note)
            
            return updated
            
        except Exception as e:
            print(f"更新卡片引用时出错: {e}")
            return False

    def backup_files(self, files: Set[Path]) -> Optional[str]:
        """备份指定文件列表"""
        try:
            if not files:
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"anki_selected_files_backup_{timestamp}"
            backup_path = Path(self.config.backup_folder) / backup_name
            
            # 创建备份目录
            backup_path.mkdir(parents=True, exist_ok=True)
            
            backup_count = 0
            for file_path in files:
                try:
                    if file_path.exists() and file_path.is_file():
                        # 计算相对路径结构
                        rel_path = None
                        
                        # 如果在媒体目录中
                        if self.media_dir in file_path.parents:
                            rel_path = file_path.relative_to(self.media_dir)
                        
                        if rel_path:
                            # 保持目录结构
                            target_dir = backup_path / "media" / rel_path.parent
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target_path = target_dir / file_path.name
                        else:
                            # 直接复制到备份根目录
                            target_path = backup_path / file_path.name
                        
                        # 复制文件
                        shutil.copy2(file_path, target_path)
                        backup_count += 1
                        
                except Exception as e:
                    print(f"备份文件失败 {file_path}: {e}")
            
            # 保存备份信息
            backup_info = {
                'timestamp': timestamp,
                'backup_type': 'selected_files',
                'media_dir': str(self.media_dir),
                'file_count': backup_count,
                'files': [str(f) for f in files],
                'total_size': sum(f.stat().st_size for f in files if f.exists())
            }
            
            import json
            info_file = backup_path / "backup_info.json"
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, indent=2, ensure_ascii=False)
            
            self.backup_dir = backup_path
            return str(backup_path)
            
        except Exception as e:
            print(f"备份文件时出错: {e}")
            return None
       
    def backup_media_folder(self) -> Optional[str]:
        """备份媒体文件夹"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"anki_media_backup_{timestamp}"
            backup_path = Path(self.config.backup_folder) / backup_name
            
            # 创建备份目录
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # 复制媒体文件
            if self.media_dir.exists():
                shutil.copytree(
                    self.media_dir,
                    backup_path / "media",
                    dirs_exist_ok=True
                )
            
            # 保存备份信息
            backup_info = {
                'timestamp': timestamp,
                'media_dir': str(self.media_dir),
                'file_count': len(list(self.media_dir.glob("*")))
            }
            
            import json
            info_file = backup_path / "backup_info.json"
            with open(info_file, 'w') as f:
                json.dump(backup_info, f, indent=2)
            
            self.backup_dir = backup_path
            return str(backup_path)
            
        except Exception as e:
            print(f"备份媒体文件夹时出错: {e}")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """从备份恢复"""
        try:
            backup_dir = Path(backup_path)
            media_backup = backup_dir / "media"
            
            if not media_backup.exists():
                return False
            
            # 清空当前媒体目录
            for item in self.media_dir.glob("*"):
                if item.is_file():
                    item.unlink()
            
            # 复制备份文件
            for item in media_backup.glob("*"):
                if item.is_file():
                    shutil.copy2(item, self.media_dir / item.name)
            
            return True
            
        except Exception as e:
            print(f"恢复备份时出错: {e}")
            return False
    
    def get_optimization_stats(self) -> Dict:
        """获取优化统计信息"""
        return {
            'total_processed': self.stats['total_processed'],
            'format_converted': self.stats['format_converted'],
            'resized': self.stats['resized'],
            'size_reduction_bytes': self.stats['size_reduction'],
            'size_reduction_mb': self.stats['size_reduction'] / (1024 * 1024),
            'original_total_size_mb': self.stats['original_total_size'] / (1024 * 1024),
            'optimized_total_size_mb': self.stats['optimized_total_size'] / (1024 * 1024),
            'compression_ratio': (
                self.stats['optimized_total_size'] / self.stats['original_total_size'] 
                if self.stats['original_total_size'] > 0 else 1.0
            )
        }
    
    def install_pillow(self) -> bool:
        """尝试安装Pillow库"""
        try:
            # 尝试通过pip安装
            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
            global HAS_PIL
            try:
                from PIL import Image
                HAS_PIL = True
                self.optimizer = ImageOptimizer(self.config)
                return True
            except ImportError:
                return False
        except Exception as e:
            print(f"安装Pillow失败: {e}")
            return False