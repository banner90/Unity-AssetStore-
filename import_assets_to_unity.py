#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unity Asset Store 资源导入工具
功能：扫描已下载的资源并导入到 Unity 项目
"""

import os
import re
import sys
import json
import shutil
import msvcrt
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)


@dataclass
class ImportConfig:
    """导入配置"""
    # 下载目录（和 download_all_assets.py 保持一致）
    DOWNLOAD_PATH: Path = Path.home() / "Downloads" / "UnityAssets"


class UnityAssetImporter:
    """Unity 资源导入器"""
    
    def __init__(self, config: ImportConfig = None):
        self.config = config or ImportConfig()
        try:
            with open("unity_downloader_config.json", "r", encoding="utf-8") as f:
                d = json.load(f)
            p = d.get("download_path")
            if p:
                self.config.DOWNLOAD_PATH = Path(p)
        except:
            pass
        self.assets: List[Dict] = []
        self.selected_index = 0
        self.scroll_top = 0
        self.page_size = 15  # 每页显示数量
    
    def scan_cached_assets(self) -> List[Dict]:
        """扫描下载目录中的所有资源"""
        print(f"[INFO] 正在扫描下载目录: {self.config.DOWNLOAD_PATH}")
        
        assets = []
        download_path = self.config.DOWNLOAD_PATH
        
        if not download_path.exists():
            print(f"[WARNING] 下载目录不存在: {download_path}")
            print(f"[INFO] 请先使用选项 1 或 2 下载资源")
            return assets
        
        # 直接从下载目录扫描 .unitypackage 文件
        for file_path in download_path.glob("*.unitypackage"):
            if not file_path.is_file():
                continue
            
            # 从文件名解析资源名和发布商
            # 文件名格式: 资源名_发布商.unitypackage
            filename = file_path.stem  # 不含扩展名
            
            # 尝试分割文件名获取资源名和发布商
            if "_" in filename:
                # 最后一个下划线后面是发布商
                parts = filename.rsplit("_", 1)
                asset_name = parts[0]
                publisher_name = parts[1] if len(parts) > 1 else "Unknown"
            else:
                asset_name = filename
                publisher_name = "Unknown"
            
            assets.append({
                'name': asset_name,
                'publisher': publisher_name,
                'path': str(file_path),
                'size': file_path.stat().st_size,
                'modified': file_path.stat().st_mtime
            })
        
        # 按修改时间排序（最新的在前）
        assets.sort(key=lambda x: x['modified'], reverse=True)
        
        print(f"[INFO] 找到 {len(assets)} 个已下载的资源")
        return assets
    
    def _format_bytes(self, size: int) -> str:
        """格式化字节大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def _clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _print_list(self):
        """打印资源列表"""
        self._clear_screen()
        
        print("=" * 80)
        print("  Unity Asset Store 资源列表")
        print("  [←↑↓→ 选择资源]  [Enter 导入]  [A 全部导入]  [Q 退出]")
        print("=" * 80)
        print()
        
        if not self.assets:
            print("  没有找到已缓存的资源")
            print()
            print("  提示：请先使用选项 1 或 2 下载资源")
            return
        
        total = len(self.assets)
        
        # 计算显示范围
        if self.selected_index < self.scroll_top:
            self.scroll_top = self.selected_index
        elif self.selected_index >= self.scroll_top + self.page_size:
            self.scroll_top = self.selected_index - self.page_size + 1
        
        start = self.scroll_top
        end = min(start + self.page_size, total)
        
        # 打印列表
        for i in range(start, end):
            asset = self.assets[i]
            size_str = self._format_bytes(asset['size'])
            name = asset['name'][:35] if len(asset['name']) > 35 else asset['name']
            publisher = asset['publisher'][:15] if len(asset['publisher']) > 15 else asset['publisher']
            
            # 选中项高亮
            if i == self.selected_index:
                print(f"  ▶ {i+1:>3}. {name:<35} {publisher:<15} {size_str:<10}")
            else:
                print(f"    {i+1:>3}. {name:<35} {publisher:<15} {size_str:<10}")
        
        # 显示滚动提示
        print()
        if total > self.page_size:
            print(f"  显示 {start+1}-{end} / 共 {total} 个")
        else:
            print(f"  共 {total} 个资源")
        print()
        
        # 显示当前选中资源详情
        if self.assets:
            selected = self.assets[self.selected_index]
            print(f"  当前选中: {selected['name']}")
            print(f"  发布商: {selected['publisher']}")
            print(f"  大小: {self._format_bytes(selected['size'])}")
            print(f"  路径: {selected['path']}")
    
    def _import_asset_to_unity(self, asset: Dict) -> bool:
        """导入单个资源到 Unity"""
        package_path = asset['path']
        
        if not os.path.exists(package_path):
            print(f"  [ERROR] 文件不存在: {package_path}")
            return False
        
        print(f"\n  [INFO] 正在导入: {asset['name']}")
        
        # 使用 Unity Editor 命令行导入
        # 方法1：尝试使用 unitypackage-importer 或直接复制
        try:
            # 检查 Unity 进程是否运行
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq Unity.exe'],
                capture_output=True,
                text=True
            )
            
            if 'Unity.exe' not in result.stdout:
                print("  [ERROR] Unity 未运行，请先打开 Unity 项目")
                return False
            
            # 尝试使用 Unity MCP (如果可用)
            # 这里我们尝试直接打开 unitypackage 文件，让 Unity 处理
            os.startfile(package_path)
            print(f"  [OK] 已在 Unity 中打开导入对话框")
            print(f"  [提示] 请在 Unity 中点击 'Import' 按钮完成导入")
            return True
            
        except Exception as e:
            print(f"  [ERROR] 导入失败: {e}")
            return False
    
    def _import_all_assets(self):
        """导入所有资源"""
        print(f"\n  [INFO] 准备导入所有 {len(self.assets)} 个资源")
        print("  [提示] 将逐个打开导入对话框，请在 Unity 中确认")
        input("  按 Enter 开始，或按 Ctrl+C 取消...")
        
        success_count = 0
        for i, asset in enumerate(self.assets, 1):
            print(f"\n  [{i}/{len(self.assets)}] {asset['name']}")
            if self._import_asset_to_unity(asset):
                success_count += 1
            if i < len(self.assets):
                input("  按 Enter 继续下一个...")
        
        print(f"\n  [完成] 成功处理 {success_count}/{len(self.assets)} 个资源")
    
    def interactive_select_and_import(self):
        """交互式选择并导入"""
        # 扫描资源
        self.assets = self.scan_cached_assets()
        
        if not self.assets:
            self._print_list()
            input("\n  按 Enter 返回...")
            return
        
        self.selected_index = 0
        self.scroll_top = 0
        
        # 显示列表并处理键盘输入
        while True:
            self._print_list()
            
            # 读取按键
            key = msvcrt.getch()
            
            # 处理方向键 (方向键是两个字节: 224 + 扫描码)
            if key == b'\xe0' or key == b'\x00':
                key = msvcrt.getch()
                
                if key == b'H':  # 上箭头
                    if self.selected_index > 0:
                        self.selected_index -= 1
                
                elif key == b'P':  # 下箭头
                    if self.selected_index < len(self.assets) - 1:
                        self.selected_index += 1
                
                elif key == b'K':  # 左箭头 - 翻页
                    total = len(self.assets)
                    current_page = self.selected_index // self.page_size
                    new_start = max(0, (current_page - 1) * self.page_size)
                    self.selected_index = min(total - 1, new_start)
                    self.scroll_top = new_start
                
                elif key == b'M':  # 右箭头 - 翻页
                    total = len(self.assets)
                    current_page = self.selected_index // self.page_size
                    total_pages = (total - 1) // self.page_size if total > 0 else 0
                    new_start = min(total_pages * self.page_size, (current_page + 1) * self.page_size)
                    self.selected_index = min(total - 1, new_start)
                    self.scroll_top = new_start
            
            # 处理普通按键
            elif key == b'\r':  # Enter - 导入当前选中
                if self.assets:
                    self._import_asset_to_unity(self.assets[self.selected_index])
                    input("\n  按 Enter 继续...")
            
            elif key == b'a' or key == b'A':  # A - 全部导入
                if self.assets:
                    self._import_all_assets()
                    input("\n  按 Enter 继续...")
            
            elif key == b'q' or key == b'Q':  # Q - 退出
                break
            
            # 长按加速滚动
            while msvcrt.kbhit():
                extra_key = msvcrt.getch()
                if extra_key == b'\xe0' or extra_key == b'\x00':
                    extra_key = msvcrt.getch()
                    if extra_key == b'H' and self.selected_index > 0:
                        self.selected_index = max(0, self.selected_index - 3)
                    elif extra_key == b'P' and self.selected_index < len(self.assets) - 1:
                        self.selected_index = min(len(self.assets) - 1, self.selected_index + 3)


def main():
    """主函数 - 供 menu.py 调用"""
    importer = UnityAssetImporter()
    importer.interactive_select_and_import()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按 Enter 退出...")
        sys.exit(1)
