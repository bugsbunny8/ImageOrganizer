"""
图片处理工具函数 - 优化版
"""

import os
import sys
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
import mimetypes

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def get_image_info(image_path: Path) -> Optional[Dict[str, Any]]:
    """获取图片信息"""
    if not HAS_PIL or not image_path.exists():
        return None
    
    try:
        with Image.open(image_path) as img:
            info = {
                'format': img.format,
                'mode': img.mode,
                'size': img.size,
                'width': img.width,
                'height': img.height,
                'color_depth': img.bits if hasattr(img, 'bits') else None,
                'has_alpha': img.mode in ('RGBA', 'LA', 'P'),
                'is_animated': getattr(img, 'is_animated', False),
                'frames': getattr(img, 'n_frames', 1)
            }
            
            # 尝试获取EXIF数据
            try:
                exif = img._getexif()
                if exif:
                    info['exif'] = exif
            except:
                pass
            
            return info
    except Exception as e:
        print(f"获取图片信息失败 {image_path}: {e}")
        return None

def estimate_size_reduction(original_path: Path, 
                          target_format: str = 'jpg',
                          quality: int = 85,
                          resolution: Tuple[int, int] = None) -> Tuple[float, int]:
    """预估压缩率"""
    if not HAS_PIL:
        return 1.0, 0
    
    try:
        original_size = original_path.stat().st_size
        
        with Image.open(original_path) as img:
            # 计算调整后的尺寸
            if resolution and resolution != (0, 0):
                orig_width, orig_height = img.size
                target_width, target_height = resolution
                
                # 等比例缩放计算
                width_ratio = target_width / orig_width
                height_ratio = target_height / orig_height
                ratio = min(width_ratio, height_ratio)
                
                if ratio < 1.0:
                    # 尺寸会缩小
                    new_width = int(orig_width * ratio)
                    new_height = int(orig_height * ratio)
                else:
                    # 不放大
                    new_width, new_height = orig_width, orig_height
                
                # 粗略估计大小减少
                size_factor = (new_width * new_height) / (orig_width * orig_height)
            else:
                size_factor = 1.0
            
            # 格式转换因子
            format_factor = 1.0
            original_format = img.format.lower() if img.format else ''
            
            if original_format in ['png', 'bmp', 'tiff'] and target_format == 'jpg':
                # PNG转JPG通常能压缩70-90%
                if img.mode in ('RGBA', 'LA', 'P'):  # 透明图片
                    format_factor = 0.3 if quality >= 80 else 0.2
                else:  # 不透明图片
                    format_factor = 0.2 if quality >= 80 else 0.15
            
            elif original_format == 'webp' and target_format == 'jpg':
                # WebP转JPG压缩率较低
                format_factor = 0.7
            
            elif original_format == 'png' and target_format == 'png':
                # PNG优化压缩
                format_factor = 0.8
            
            # 质量因子
            quality_factor = quality / 100.0
            
            # 综合估计
            estimated_ratio = size_factor * format_factor * quality_factor
            estimated_size = int(original_size * estimated_ratio)
            estimated_savings = original_size - estimated_size
            
            return min(1.0, max(0.1, estimated_ratio)), estimated_savings
            
    except Exception as e:
        print(f"预估压缩率失败: {e}")
        return 1.0, 0

def estimate_savings_by_extension(file_path: Path, file_size: int) -> int:
    """根据文件扩展名快速预估节省空间"""
    ext = file_path.suffix.lower()
    
    # PNG、BMP、TIFF等无损格式转换为JPG可以大幅节省空间
    if ext in ['.png', '.bmp', '.tiff', '.tif']:
        # PNG转JPG通常可以节省70-80%
        return int(file_size * 0.75)  # 预估节省75%
    
    # JPG/JPEG文件通过优化可以节省10-30%
    elif ext in ['.jpg', '.jpeg']:
        # JPG优化可以节省20%
        return int(file_size * 0.2)
    
    # WebP转换为JPG可以节省一些空间
    elif ext == '.webp':
        return int(file_size * 0.3)  # 预估节省30%
    
    # GIF动画优化
    elif ext == '.gif':
        return int(file_size * 0.1)  # 预估节省10%
    
    # 其他格式转换效果不明显
    else:
        return 0

def is_transparent_image(image_path: Path) -> bool:
    """检查图片是否透明"""
    if not HAS_PIL:
        return False
    
    try:
        with Image.open(image_path) as img:
            if img.mode in ('RGBA', 'LA'):
                # 检查是否有透明像素
                alpha = img.getchannel('A')
                return any(pixel < 255 for pixel in alpha.getdata())
            elif img.mode == 'P':
                # 调色板模式可能透明
                return img.info.get('transparency') is not None
        return False
    except:
        return False

def get_recommended_settings(image_path: Path) -> Dict[str, Any]:
    """获取推荐的优化设置"""
    info = get_image_info(image_path)
    if not info:
        return {}
    
    recommendations = {
        'convert_to_jpg': False,
        'target_format': info['format'],
        'recommended_quality': 85,
        'should_resize': False,
        'recommended_resolution': info['size']
    }
    
    # 检查是否需要转换格式
    if info['format'] and info['format'].lower() in ['png', 'bmp', 'tiff']:
        if not info['has_alpha'] and not info['is_animated']:
            recommendations['convert_to_jpg'] = True
            recommendations['target_format'] = 'JPEG'
    
    # 检查是否需要调整分辨率
    width, height = info['size']
    if width > 1920 or height > 1080:
        recommendations['should_resize'] = True
        # 推荐保持宽高比的1080p内尺寸
        if width > height:  # 横屏
            recommendations['recommended_resolution'] = (1920, int(height * 1920 / width))
        else:  # 竖屏
            recommendations['recommended_resolution'] = (int(width * 1080 / height), 1080)
    
    # 根据格式调整质量
    if recommendations['target_format'] == 'JPEG':
        if info['mode'] == 'L':  # 灰度图
            recommendations['recommended_quality'] = 90
        elif width * height > 2000000:  # 大图
            recommendations['recommended_quality'] = 80
        else:
            recommendations['recommended_quality'] = 85
    
    return recommendations

def batch_estimate_savings(image_paths: List[Path], 
                          target_format: str = 'jpg',
                          quality: int = 85) -> Dict[str, Any]:
    """批量预估节省空间"""
    total_original = 0
    total_estimated = 0
    
    for path in image_paths:
        if path.exists():
            original_size = path.stat().st_size
            total_original += original_size
            
            ratio, _ = estimate_size_reduction(path, target_format, quality)
            total_estimated += original_size * ratio
    
    savings = total_original - total_estimated
    
    return {
        'total_original_mb': total_original / (1024 * 1024),
        'total_estimated_mb': total_estimated / (1024 * 1024),
        'savings_mb': savings / (1024 * 1024),
        'compression_ratio': total_estimated / total_original if total_original > 0 else 1.0
    }

def safe_filename(filename: str, max_length: int = 255) -> str:
    """生成安全的文件名"""
    # 移除非法字符
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    
    # 限制长度
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        name = name[:max_length - len(ext)]
        filename = name + ext
    
    return filename

def format_size(size_in_bytes: int) -> str:
    """格式化文件大小"""
    if size_in_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    
    return f"{size_in_bytes:.1f} TB"

def format_size_simple(size_in_bytes: int) -> str:
    """简化文件大小格式化"""
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    elif size_in_bytes < 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.1f} GB"

def get_file_hash_fast(filepath: Path, algorithm: str = "md5", 
                      sample_size: int = 1024*1024) -> str:
    """快速计算文件哈希（只读取部分数据）"""
    import hashlib
    
    try:
        hash_func = hashlib.new(algorithm)
        file_size = filepath.stat().st_size
        
        with open(filepath, 'rb') as f:
            # 读取文件开头
            chunk = f.read(min(sample_size, file_size))
            hash_func.update(chunk)
            
            # 如果文件较大，再读取中间和结尾部分
            if file_size > sample_size * 2:
                # 跳转到中间
                f.seek(file_size // 2)
                chunk = f.read(min(sample_size, file_size // 2))
                hash_func.update(chunk)
                
                # 跳转到结尾
                f.seek(-min(sample_size, file_size), 2)
                chunk = f.read(min(sample_size, file_size))
                hash_func.update(chunk)
        
        return hash_func.hexdigest()[:12]  # 返回前12位，足够用于文件名
    except Exception as e:
        print(f"快速计算文件哈希失败 {filepath}: {e}")
        return ""