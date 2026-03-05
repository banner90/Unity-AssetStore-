#!/usr/bin/env python3
"""
Unity Asset Store 一键下载脚本
智能模式：自动跳过已存在的，重试失败的，下载新的
"""

import asyncio
import json
import sys
import shutil
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from playwright.async_api import async_playwright, Download

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)

# 颜色
GREEN = '\033[92m'
RED = '\033[91m'  
CYAN = '\033[96m'
YELLOW = '\033[93m'
RESET = '\033[0m'
CLEAR = '\033[K'

# 盲文转圈
SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

@dataclass
class Config:
    DOWNLOAD_PATH: Path = Path.home() / "Downloads" / "UnityAssets"
    COOKIES_FILE: Path = Path("unity_cookies.json")
    FAILED_FILE: Path = Path("unity_failed_downloads.json")
    MY_ASSETS_URL: str = "https://assetstore.unity.com/account/assets"
    HEADLESS: bool = False  # True = 不显示浏览器窗口
    BROWSER: str = "chromium"  # 可选：chromium / chrome / edge
    STORAGE_STATE_FILE: Path = Path("unity_storage_state.json")

class Downloader:
    def __init__(self, config: Config):
        self.config = config
        self.total = 0
        self.completed = 0  # 包括已存在的和本次下载成功的
        self.failed = 0
        self.new_downloaded = 0  # 本次新下载的数量
        self.existing = 0  # 已存在的数量
        self.current_num = 0
        self.current_file = ""
        self.failed_files = set()
        self.completed_files = set()
        
        self._load_records()
        
    def _load_records(self):
        """加载记录"""
        # 扫描已下载的文件
        if self.config.DOWNLOAD_PATH.exists():
            for f in self.config.DOWNLOAD_PATH.iterdir():
                if f.is_file() and f.suffix == '.unitypackage':
                    self.completed_files.add(f.name)
        
        # 加载失败记录
        if self.config.FAILED_FILE.exists():
            try:
                with open(self.config.FAILED_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for r in data:
                    if r.get('status') == 'failed':
                        self.failed_files.add(r['filename'])
                # 移除已经下载成功的
                self.failed_files -= self.completed_files
            except:
                pass
    
    def _check_disk_space(self) -> tuple:
        """检查磁盘空间，返回 (剩余空间GB, 是否需要警告)"""
        try:
            # 获取下载目录所在磁盘
            download_path = self.config.DOWNLOAD_PATH
            download_path.mkdir(parents=True, exist_ok=True)
            
            # 获取磁盘使用情况
            usage = shutil.disk_usage(download_path)
            free_gb = usage.free / (1024**3)  # 转换为GB
            total_gb = usage.total / (1024**3)
            
            # 计算预估需要的空间
            # 假设每个资源平均 50MB（Unity资源一般 10MB-500MB 不等）
            remaining = self.total - len(self.completed_files)
            avg_size_mb = 50  # 平均50MB
            needed_gb = (remaining * avg_size_mb) / 1024
            
            # 如果剩余空间小于预估需要的1.5倍，发出警告
            need_warning = free_gb < (needed_gb * 1.5)
            
            return free_gb, total_gb, needed_gb, need_warning
        except Exception as e:
            return 0, 0, 0, False
    
    def _save_failed(self):
        """保存失败记录"""
        try:
            records = []
            for filename in self.failed_files:
                records.append({
                    'filename': filename,
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                })
            with open(self.config.FAILED_FILE, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        except:
            pass
        
    def _print(self, status: str, filename: str, size_mb: float = 0):
        """打印状态"""
        current = self.completed + self.failed
        if status == 'downloading':
            return
        if status == 'existing':
            size = f" ({size_mb:.1f}MB)" if size_mb > 0 else ""
            text = f"[{current}/{self.total}] 已有 {filename[:45]}{size}"
            print(f"{GREEN}{text}{RESET}")
        elif status == 'completed':
            size = f" ({size_mb:.1f}MB)" if size_mb > 0 else ""
            text = f"[{current}/{self.total}] 成功 {filename[:45]}{size}"
            print(f"{GREEN}{text}{RESET}")
        elif status == 'failed':
            text = f"[{current}/{self.total}] 失败 {filename[:45]}"
            print(f"{RED}{text}{RESET}")
    
    async def handle_download(self, download: Download):
        """处理下载"""
        filename = download.suggested_filename
        file_path = self.config.DOWNLOAD_PATH / filename
        
        # 文件已存在且完整
        if file_path.exists() and file_path.stat().st_size > 0:
            self.existing += 1
            self.completed += 1
            self.current_file = filename
            size_mb = file_path.stat().st_size / (1024 * 1024)
            self._print('existing', filename, size_mb)
            self.failed_files.discard(filename)
            try:
                await download.cancel()
            except:
                pass
            return
        
        # 需要下载
        self.current_file = filename
        
        # 使用 download.path() 获取原始下载文件路径，完成后直接移动为目标文件名，避免双份占用
        download_task = asyncio.create_task(download.path())
        
        # 等待下载完成，带超时保护（5分钟）
        max_wait = 3000  # 5分钟 = 3000 * 0.1秒
        wait_count = 0
        
        while not download_task.done() and wait_count < max_wait:
            await asyncio.sleep(0.1)
            wait_count += 1
        
        # 如果超时了，取消任务
        if not download_task.done():
            download_task.cancel()
            try:
                await download_task
            except asyncio.CancelledError:
                pass
            self.failed += 1
            self.failed_files.add(filename)
            self._print('failed', filename)
            return
        
        # 检查任务结果
        try:
            temp_path = await download_task
            
            # 如果拿不到临时文件路径，退回到 save_as 复制方案
            if not temp_path:
                await download.save_as(file_path)
            else:
                try:
                    # 若目标已存在（极少数竞态），以目标为准，清理原始文件
                    if file_path.exists():
                        try:
                            Path(temp_path).unlink()
                        except:
                            pass
                    else:
                        shutil.move(temp_path, file_path)
                except:
                    # 失败时退回到 save_as
                    await download.save_as(file_path)
            
            # 检查文件是否真的下载成功了
            if not file_path.exists() or file_path.stat().st_size == 0:
                raise Exception("Download file not created or empty")
            
            size_mb = file_path.stat().st_size / (1024 * 1024)
            self.completed += 1
            self.new_downloaded += 1
            self.completed_files.add(filename)
            self.failed_files.discard(filename)
            self._print('completed', filename, size_mb)
            
        except asyncio.CancelledError:
            # 被取消（比如文件已存在时）
            pass
        except Exception as e:
            self.failed += 1
            self.failed_files.add(filename)
            self._print('failed', filename)
    
    async def run(self):
        async with async_playwright() as p:
            self.config.DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
            
            # 根据选择的浏览器启动
            if self.config.BROWSER == "edge":
                browser = await p.chromium.launch(
                    channel="msedge",
                    headless=self.config.HEADLESS,
                    downloads_path=str(self.config.DOWNLOAD_PATH)
                )
            elif self.config.BROWSER == "chrome":
                browser = await p.chromium.launch(
                    channel="chrome",
                    headless=self.config.HEADLESS,
                    downloads_path=str(self.config.DOWNLOAD_PATH)
                )
            else:
                browser = await p.chromium.launch(
                    headless=self.config.HEADLESS,
                    downloads_path=str(self.config.DOWNLOAD_PATH)
                )
            
            if self.config.STORAGE_STATE_FILE.exists():
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    accept_downloads=True,
                    storage_state=str(self.config.STORAGE_STATE_FILE)
                )
            else:
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    accept_downloads=True
                )
            
            if not self.config.STORAGE_STATE_FILE.exists() and self.config.COOKIES_FILE.exists():
                try:
                    with open(self.config.COOKIES_FILE, 'r') as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                except:
                    pass
            
            page = await context.new_page()
            
            # 登录
            print(CYAN + "打开 Asset Store..." + RESET)
            try:
                await page.goto(self.config.MY_ASSETS_URL, wait_until="domcontentloaded", timeout=30000)
            except:
                pass
            await asyncio.sleep(2)
            
            if 'account/assets' not in page.url:
                print(CYAN + "请登录 Unity 账户，完成后按 Enter..." + RESET)
                for i in range(150):
                    await asyncio.sleep(2)
                    if 'account/assets' in page.url:
                        print(GREEN + "登录成功" + RESET)
                        break
                else:
                    try:
                        input()
                    except:
                        pass
            else:
                print(GREEN + "已登录" + RESET)
            
            if 'account/assets' not in page.url:
                print(RED + "登录失败" + RESET)
                await browser.close()
                return
            
            try:
                await context.storage_state(path=str(self.config.STORAGE_STATE_FILE))
            except:
                pass
            
            # 获取总数
            import re
            try:
                page_text = await page.evaluate('() => document.body.innerText.slice(0, 3000)')
                match = re.search(r'(\d+)\s*项中', page_text)
                if match:
                    self.total = int(match.group(1))
                    remaining = self.total - len(self.completed_files)
                    print(f"\n共 {self.total} 个资源，已完成 {len(self.completed_files)} 个，剩余 {remaining} 个")
            except:
                pass
            
            # 检查磁盘空间
            free_gb, total_gb, needed_gb, need_warning = self._check_disk_space()
            if free_gb > 0:
                print(f"\n磁盘空间检查:")
                print(f"  下载位置: {self.config.DOWNLOAD_PATH}")
                print(f"  磁盘总空间: {total_gb:.1f} GB")
                print(f"  剩余空间: {GREEN if free_gb > needed_gb * 2 else (YELLOW if free_gb > needed_gb else RED)}{free_gb:.1f} GB{RESET}")
                print(f"  请保证空间足够")
                
                if need_warning:
                    print(f"\n{YELLOW}警告: 磁盘空间可能不足！{RESET}")
                    print(f"建议清理磁盘或更改下载路径后再继续。")
                    response = input(f"\n是否继续下载? (y/n): ").strip().lower()
                    if response not in ('y', 'yes', '是'):
                        print("已取消下载")
                        await browser.close()
                        return
                else:
                    print(f"{GREEN}磁盘空间充足{RESET}")
                print()
            
            # 找按钮（等待页面渲染完成）
            selectors = [
                'button:has-text("下载所有资源")',
                'button:has-text("Download all")',
            ]
            
            btn = None
            print(CYAN + "正在等待下载按钮出现..." + RESET)
            for i in range(120):
                for sel in selectors:
                    try:
                        if await page.locator(sel).count() > 0:
                            btn = sel
                            break
                    except:
                        pass
                if btn:
                    break
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except:
                    pass
                if i % 15 == 0:
                    try:
                        await page.goto(self.config.MY_ASSETS_URL, wait_until="domcontentloaded", timeout=30000)
                    except:
                        pass
                await asyncio.sleep(1)
            
            if not btn:
                print(RED + "未找到下载按钮" + RESET)
                await browser.close()
                return
            
            print(CYAN + "开始下载...\n" + RESET)
            
            page.on("download", lambda d: asyncio.create_task(self.handle_download(d)))
            await page.click(btn)
            await asyncio.sleep(3)
            
            # 等待下载完成
            last_completed = 0
            no_change = 0
            idle_mode = False
            # 记录当前下载目录中文件数量作为参考（不作为计数依据，仅用于唤醒监听）
            try:
                last_fs_count = sum(1 for f in self.config.DOWNLOAD_PATH.glob("*.unitypackage"))
            except:
                last_fs_count = 0
            
            while True:
                await asyncio.sleep(15 if idle_mode else 3)
                
                total = self.completed + self.failed
                if total > last_completed:
                    no_change = 0
                    last_completed = total
                    if idle_mode:
                        print(CYAN + "\n检测到新的下载进展，恢复监听模式" + RESET)
                        idle_mode = False
                else:
                    no_change += 1
                
                if self.total > 0 and total >= self.total:
                    break
                
                # 长时间无变化则进入空闲监测模式，不退出浏览器
                if not idle_mode and no_change > 60:  # 约3分钟无变化
                    idle_mode = True
                    print(YELLOW + "\n长时间无新进展，保持页面打开并后台等待（按 Ctrl+C 退出）" + RESET)
                
                # 空闲模式下定期检测目录变化，若发现新文件则唤醒监听
                if idle_mode:
                    try:
                        fs_count = sum(1 for f in self.config.DOWNLOAD_PATH.glob("*.unitypackage"))
                    except:
                        fs_count = last_fs_count
                    if fs_count > last_fs_count:
                        print(CYAN + "\n检测到下载目录有新文件，恢复监听模式" + RESET)
                        idle_mode = False
                    last_fs_count = fs_count
                
                try:
                    _ = await page.title()  # 保持与页面的心跳
                except:
                    # 即使获取标题失败，也不主动退出，继续等待
                    pass
            
            # 保存
            cookies = await context.cookies()
            with open(self.config.COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
            try:
                await context.storage_state(path=str(self.config.STORAGE_STATE_FILE))
            except:
                pass
            self._save_failed()
            await browser.close()
            
            print()
            print("=" * 50)
            print(f"本次下载: {GREEN}{self.new_downloaded}{RESET}")
            print(f"已有文件: {GREEN}{self.existing}{RESET}")
            print(f"失败: {RED}{self.failed}{RESET}")
            print(f"总计完成: {GREEN}{self.completed}{RESET}/{self.total}")
            print(f"保存位置: {self.config.DOWNLOAD_PATH}")
            print("=" * 50)

async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Unity Asset Store 批量下载')
    parser.add_argument('--headless', action='store_true', help='无头模式（不显示浏览器窗口）')
    parser.add_argument('--browser', choices=['chromium', 'chrome', 'edge'], default='chromium', help='选择浏览器：chromium/chrome/edge')
    parser.add_argument('--download-path', type=str, help='下载保存路径')
    args = parser.parse_args()
    
    if args.headless:
        print(CYAN + "Unity Asset Store 批量下载 (无头模式)" + RESET)
    else:
        print(CYAN + "Unity Asset Store 批量下载" + RESET)
    print()
    
    config = Config()
    config.HEADLESS = args.headless
    config.BROWSER = args.browser
    if args.download_path:
        try:
            config.DOWNLOAD_PATH = Path(args.download_path)
        except:
            pass
    try:
        with open("unity_downloader_config.json", "w", encoding="utf-8") as f:
            json.dump({"download_path": str(config.DOWNLOAD_PATH)}, f, ensure_ascii=False, indent=2)
    except:
        pass
    downloader = Downloader(config)
    await downloader.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")
    except Exception as e:
        print(f"\n错误: {e}")
