"""
卡片扫描器 - 支持范围选择和文件信息收集
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set, Union
from dataclasses import dataclass, field
import html
from collections import defaultdict
import hashlib

from aqt import mw
from aqt.utils import showInfo, showWarning

@dataclass
class ImageReference:
    """图片引用信息"""
    card_id: int
    note_id: int
    field_index:int
    field_name: str
    field_content: str
    original_path: str
    new_path: Optional[str] = None
    file_exists: bool = False
    is_local: bool = False
    error: Optional[str] = None
    file_size: int = 0  # 文件大小（字节）
    file_hash: Optional[str] = None  # 文件哈希值
    estimated_savings: int = 0  # 预估节省空间（字节）
    estimated_new_filename: Optional[str] = None  # 预估新文件名

@dataclass
class ScanScope:
    """扫描范围"""
    scope_type: str  # all, current_deck, selected_decks, selected_cards, custom_search
    deck_ids: List[int] = field(default_factory=list)
    card_ids: List[int] = field(default_factory=list)
    search_query: str = None
    include_subdecks: bool = True
    limit: int = 0  # 0表示无限制

class CardScanner:
    """卡片扫描器 - 增强版"""
    
    def __init__(self):
        self.media_dir = self.get_media_directory()
        self.config = {
            'img_patterns': [
                r'<img[^>]+src="([^"]+)"[^>]*>',
                r'<img[^>]+src=\'([^\']+)\'[^>]*>',
                r'\[sound:([^\]]+)\]',
            ],
            'ignore_patterns': [
                'http://', 'https://', 'data:image'
            ]
        }
    
    def get_media_directory(self) -> Path:
        """获取媒体目录"""
        if mw and mw.col:
            media_dir = Path(mw.col.media.dir())
            if media_dir.exists():
                return media_dir
        # 备用方法
        return Path.home() / 'AppData/Roaming/Anki2/User 1/collection.media'
    
    def get_scope_cards(self, scope: ScanScope) -> List[int]:
        """根据范围获取卡片ID列表"""
        if not mw or not mw.col:
            return []
        
        try:
            if scope.scope_type == "all":
                # 所有卡片
                search = ""
                
            elif scope.scope_type == "current_deck":
                # 当前牌组
                current_deck = mw.col.decks.current()
                if current_deck:
                    deck_name = mw.col.decks.name(current_deck['id'])
                    if scope.include_subdecks:
                        search = f'"deck:{deck_name}"'
                    else:
                        search = f'deck:"{deck_name}"'
                else:
                    search = ""
                
            elif scope.scope_type == "selected_decks":
                # 指定牌组
                if scope.deck_ids:
                    deck_names = []
                    for deck_id in scope.deck_ids:
                        try:
                            deck_name = mw.col.decks.name(deck_id)
                            if scope.include_subdecks:
                                deck_names.append(f'"deck:{deck_name}"')
                            else:
                                deck_names.append(f'deck:"{deck_name}"')
                        except:
                            continue
                    
                    if deck_names:
                        search = " or ".join(deck_names)
                    else:
                        return []
                else:
                    return []
                
            elif scope.scope_type == "selected_cards":
                # 选中卡片
                if scope.card_ids:
                    return scope.card_ids
                else:
                    return []
                
            elif scope.scope_type == "custom_search":
                # 自定义搜索
                if scope.search_query:
                    search = scope.search_query
                else:
                    return []
            
            else:
                # 未知范围类型
                return []
            
            # 执行搜索
            if scope.scope_type != "selected_cards":
                card_ids = mw.col.find_cards(search)
            else:
                card_ids = scope.card_ids
            
            # 应用限制
            if scope.limit > 0 and len(card_ids) > scope.limit:
                card_ids = card_ids[:scope.limit]
            
            return card_ids
            
        except Exception as e:
            print(f"获取卡片范围时出错: {e}")
            return []
    
    def scan_scope(self, scope: ScanScope, 
                  calculate_hash: bool = True) -> List[Dict]:
        """扫描指定范围的卡片"""
        card_ids = self.get_scope_cards(scope)
        
        if not card_ids:
            return []
        
        all_cards = []
        total_cards = len(card_ids)
        
        # 分批处理，避免内存问题
        batch_size = 100
        for i in range(0, total_cards, batch_size):
            batch_ids = card_ids[i:i+batch_size]
            
            for card_id in batch_ids:
                try:
                    card = mw.col.get_card(card_id)
                    if card:
                        card_info = self.scan_card(card, calculate_hash)
                        if card_info:
                            all_cards.append(card_info)
                except Exception as e:
                    print(f"扫描卡片 {card_id} 时出错: {e}")
            
            # 更新进度（如果需要UI显示）
            if hasattr(self, 'progress_callback'):
                self.progress_callback(i + len(batch_ids), total_cards)
        
        return all_cards
    
    def scan_all_cards(self) -> List[Dict]:
        """扫描所有卡片（兼容旧版）"""
        scope = ScanScope(scope_type="all")
        return self.scan_scope(scope)
    
    def scan_current_deck(self, include_subdecks: bool = True) -> List[Dict]:
        """扫描当前牌组"""
        scope = ScanScope(
            scope_type="current_deck",
            include_subdecks=include_subdecks
        )
        return self.scan_scope(scope)
    
    def scan_selected_decks(self, deck_ids: List[int], include_subdecks: bool = True) -> List[Dict]:
        """扫描指定牌组"""
        scope = ScanScope(
            scope_type="selected_decks",
            deck_ids=deck_ids,
            include_subdecks=include_subdecks
        )
        return self.scan_scope(scope)
    
    def scan_selected_cards(self, card_ids: List[int]) -> List[Dict]:
        """扫描选中卡片"""
        scope = ScanScope(
            scope_type="selected_cards",
            card_ids=card_ids
        )
        return self.scan_scope(scope)
    
    def scan_custom_search(self, search_query: str) -> List[Dict]:
        """扫描自定义搜索"""
        scope = ScanScope(
            scope_type="custom_search",
            search_query=search_query
        )
        return self.scan_scope(scope)
    
    def get_deck_list(self) -> List[Dict]:
        """获取牌组列表"""
        if not mw or not mw.col:
            return []
        
        decks = []
        try:
            all_decks = mw.col.decks.all()
            
            for deck in all_decks:
                # 获取牌组的真实卡片数
                deck_id = deck['id']
                try:
                    # 使用Anki的API获取牌组的真实卡片数
                    # 包括子牌组的卡片
                    card_count = mw.col.decks.card_count(deck_id, include_subdecks=True)
                except:
                    # 如果API不可用，使用默认值
                    card_count = deck.get('card_count', 0)

                deck_info = {
                    'id': deck['id'],
                    'name': deck['name'],
                    'card_count': card_count,  # 使用真实卡片数,
                    'is_dynamic': deck.get('dyn', 0) == 1,
                    'parent': self._get_deck_parent(deck['name'])
                }
                decks.append(deck_info)
            
            # 按名称排序
            decks.sort(key=lambda x: x['name'].lower())
            
        except Exception as e:
            print(f"获取牌组列表时出错: {e}")
        
        return decks
    
    def _get_deck_parent(self, deck_name: str) -> str:
        """获取牌组父级名称"""
        if '::' in deck_name:
            parts = deck_name.split('::')
            return '::'.join(parts[:-1])
        return ""
    
    def get_selected_cards_from_browser(self) -> List[int]:
        """从卡片浏览器获取选中卡片"""
        try:
            # 尝试获取当前卡片浏览器窗口
            from aqt import browser
            if hasattr(browser, '_currentBrowser'):
                browser_window = browser._currentBrowser
                if browser_window:
                    return browser_window.selectedCards()
            
            # 备用方法：检查全局变量
            if hasattr(mw, '_browser') and mw._browser:
                return mw._browser.selectedCards()
            
        except Exception as e:
            print(f"获取浏览器选中卡片时出错: {e}")
        
        return []
    
    def get_current_deck_id(self) -> Optional[int]:
        """获取当前牌组ID"""
        if not mw or not mw.col:
            return None
        
        try:
            current_deck = mw.col.decks.current()
            if current_deck:
                return current_deck['id']
        except:
            pass
        
        return None
    
    def estimate_scope_size(self, scope: ScanScope) -> Dict:
        """预估范围大小"""
        try:
            card_ids = self.get_scope_cards(scope)
            
            if not card_ids:
                return {
                    'card_count': 0,
                    'estimated_time': 0,
                    'estimated_images': 0
                }
            
            # 抽样估算图片数量
            sample_size = min(100, len(card_ids))
            sample_ids = card_ids[:sample_size]
            
            image_count = 0
            for card_id in sample_ids[:10]:  # 只检查前10个作为样本
                try:
                    card = mw.col.get_card(card_id)
                    if card:
                        note = card.note()
                        for field in note.fields:
                            images = self.extract_images(field)
                            image_count += len(images)
                except:
                    pass
            
            # 估算总图片数
            if sample_ids:
                avg_images_per_card = image_count / min(10, len(sample_ids))
            else:
                avg_images_per_card = 0
            
            total_images = int(avg_images_per_card * len(card_ids))
            
            # 估算处理时间（假设每个图片0.5秒）
            estimated_time = total_images * 0.5 / 60  # 转换为分钟
            
            return {
                'card_count': len(card_ids),
                'estimated_images': total_images,
                'estimated_time_minutes': round(estimated_time, 1),
                'sample_size': sample_size
            }
            
        except Exception as e:
            print(f"预估范围大小时出错: {e}")
            return {
                'card_count': 0,
                'estimated_time': 0,
                'estimated_images': 0
            }
    
    def scan_card(self, card, calculate_hash: bool = True) -> Optional[Dict]:
        """扫描单个卡片"""
        try:
            note = card.note()
            note_id = note.id
            model = note.note_type()
            
            card_info = {
                'card_id': card.id,
                'note_id': note_id,
                'model_name': model['name'],
                'deck_name': mw.col.decks.name(card.did) if hasattr(card, 'did') else '',
                'fields': {},
                'images': []
            }
            
            # 扫描每个字段
            for field_index, field_name in enumerate(model['flds']):
                field_content = note.fields[field_index]
                field_info = {
                    'name': field_name['name'],
                    'content': field_content,
                    'images': []
                }
                
                # 提取图片引用
                images = self.extract_images(field_content)
                for img_info in images:
                    image_ref = ImageReference(
                        card_id=card.id,
                        note_id=note_id,
                        field_index=field_index,
                        field_name=field_name['name'],
                        field_content=field_content,
                        original_path=img_info['path'],
                        file_exists=img_info['exists'],
                        is_local=img_info['is_local'],
                        file_size=img_info.get('size', 0),
                        file_hash=img_info.get('hash'),
                        estimated_savings=img_info.get('estimated_savings', 0)
                    )
                    field_info['images'].append(image_ref)
                    card_info['images'].append(image_ref)
                
                card_info['fields'][field_name['name']] = field_info
            
            return card_info if card_info['images'] else None
            
        except Exception as e:
            print(f"扫描卡片 {card.id} 时出错: {e}")
            return None
    
    def extract_images(self, content: str) -> List[Dict]:
        """从内容中提取图片引用"""
        images = []
        
        if not content:
            return images
        
        # 解码HTML实体
        content = html.unescape(content)
        
        # 匹配所有图片标签
        img_patterns = [
            (r'<img[^>]+src="([^"]+)"[^>]*>', 'src'),
            (r'<img[^>]+src=\'([^\']+)\'[^>]*>', 'src'),
            #(r'src="([^"]+)"', 'src'),  # 通用src属性
        ]
        
        for pattern, attr in img_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # 处理可能的多重匹配
                if isinstance(match, tuple):
                    path = match[0] if match else ""
                else:
                    path = match
                
                if path:
                    img_info = self.analyze_image_path(path)
                    if img_info and img_info['is_local']:
                        images.append(img_info)
        
        # 匹配音频文件（可能包含在图片字段中）
        audio_pattern = r'\[sound:([^\]]+)\]'
        audio_matches = re.findall(audio_pattern, content)
        for audio_path in audio_matches:
            if audio_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                img_info = self.analyze_image_path(audio_path)
                if img_info and img_info['is_local']:
                    images.append(img_info)
        
        return images
    
    def analyze_image_path(self, path: str) -> Optional[Dict]:
        """分析图片路径"""
        # 检查是否应忽略
        for ignore in self.config['ignore_patterns']:
            if ignore in path.lower():
                return None
        
        # 清理路径
        path = path.strip()
        if not path:
            return None
        
        # 判断是否为本地文件
        is_local = True
        if path.startswith(('http://', 'https://', '//', 'data:')):
            is_local = False
            return None
        
        # 获取文件名
        filename = path.split('?')[0].split('#')[0]  # 移除查询参数和锚点
        filename = Path(filename).name
        
        # 检查文件是否存在
        file_exists = False
        file_path = None
        file_size = 0
        file_hash = None
        estimated_savings = 0
        
        if self.media_dir:
            # 尝试在媒体目录中查找
            media_path = self.media_dir / filename
            if media_path.exists() and media_path.is_file():
                file_exists = True
                file_path = str(media_path)
                
                # 获取文件大小
                try:
                    file_size = media_path.stat().st_size
                    
                    # 计算文件哈希（可选，用于预估文件名）
                    try:
                        # 快速哈希计算（只读取前1MB）
                        file_hash = self.calculate_file_hash_fast(media_path)
                        
                        # 预估节省空间（根据文件类型）
                        estimated_savings = self.estimate_savings(media_path, file_size)
                    except Exception as e:
                        print(f"计算文件哈希或预估节省时出错 {media_path}: {e}")
                except Exception as e:
                    print(f"获取文件大小时出错 {media_path}: {e}")
                    
            else:
                # 尝试完整路径
                try:
                    full_path = Path(path)
                    if full_path.exists() and full_path.is_file():
                        file_exists = True
                        file_path = str(full_path)
                        
                        # 获取文件大小
                        try:
                            file_size = full_path.stat().st_size
                            
                            # 计算文件哈希
                            try:
                                file_hash = self.calculate_file_hash_fast(full_path)
                                estimated_savings = self.estimate_savings(full_path, file_size)
                            except:
                                pass
                        except:
                            pass
                except:
                    pass
        
        return {
            'path': path,
            'filename': filename,
            'file_path': file_path,
            'exists': file_exists,
            'is_local': is_local,
            'size': file_size,
            'hash': file_hash,
            'estimated_savings': estimated_savings
        }
    
    def calculate_file_hash_fast(self, file_path: Path, chunk_size: int = 1024*1024) -> str:
        """快速计算文件哈希（只读取部分数据）"""
        try:
            hash_md5 = hashlib.md5()
            
            with open(file_path, 'rb') as f:
                # 读取文件开头
                chunk = f.read(chunk_size)
                hash_md5.update(chunk)
                
                # 如果文件较大，再读取中间和结尾部分
                file_size = file_path.stat().st_size
                if file_size > chunk_size * 2:
                    # 跳转到中间
                    f.seek(file_size // 2)
                    chunk = f.read(chunk_size)
                    hash_md5.update(chunk)
                    
                    # 跳转到结尾
                    f.seek(-chunk_size, 2)
                    chunk = f.read(chunk_size)
                    hash_md5.update(chunk)
            
            return hash_md5.hexdigest()[:12]  # 返回前12位，足够用于文件名
        except Exception as e:
            print(f"快速计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def estimate_savings(self, file_path: Path, file_size: int) -> int:
        """预估节省空间"""
        try:
            # 根据文件扩展名预估
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
            
            # 其他格式转换效果不明显
            else:
                return 0
                
        except Exception as e:
            print(f"预估节省空间失败 {file_path}: {e}")
            return 0
    
    def get_statistics(self, cards: List[Dict]) -> Dict:
        """获取统计信息"""
        total_cards = len(cards)
        total_images = 0
        existing_images = 0
        missing_images = 0
        unique_files = set()
        total_file_size = 0
        total_estimated_savings = 0
        
        # 按牌组统计
        deck_stats = defaultdict(lambda: {
            'card_count': 0,
            'image_count': 0,
            'file_size': 0,
            'estimated_savings': 0
        })
        
        for card in cards:
            deck_name = card.get('deck_name', '未知牌组')
            deck_stats[deck_name]['card_count'] += 1
            
            for image_ref in card['images']:
                total_images += 1
                deck_stats[deck_name]['image_count'] += 1
                
                if image_ref.file_exists:
                    existing_images += 1
                    if image_ref.original_path:
                        unique_files.add(image_ref.original_path)
                    
                    # 文件大小
                    total_file_size += image_ref.file_size
                    deck_stats[deck_name]['file_size'] += image_ref.file_size
                    
                    # 预估节省
                    total_estimated_savings += image_ref.estimated_savings
                    deck_stats[deck_name]['estimated_savings'] += image_ref.estimated_savings
                else:
                    missing_images += 1
        
        # 转换为MB
        total_file_size_mb = total_file_size / (1024 * 1024)
        total_estimated_savings_mb = total_estimated_savings / (1024 * 1024)
        
        return {
            'total_cards': total_cards,
            'total_images': total_images,
            'existing_images': existing_images,
            'missing_images': missing_images,
            'unique_files': len(unique_files),
            'total_file_size_bytes': total_file_size,
            'total_file_size_mb': round(total_file_size_mb, 2),
            'total_estimated_savings_bytes': total_estimated_savings,
            'total_estimated_savings_mb': round(total_estimated_savings_mb, 2),
            'estimated_compression_ratio': round(total_estimated_savings / total_file_size * 100, 1) if total_file_size > 0 else 0,
            'deck_stats': dict(deck_stats)
        }