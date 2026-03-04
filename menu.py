#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unity Asset Store 下载器 - 中文菜单
"""

import os
import sys
import subprocess

# 设置 Windows 控制台 UTF-8 编码
if os.name == 'nt':
    os.system('chcp 65001 >nul 2>&1')
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', write_through=True)


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印标题"""
    # 红色 ANSI 转义码
    RED = '\033[91m'
    RESET = '\033[0m'
    
    print(RED + "=" * 50 + RESET)
    print(RED + "革命不是请客吃饭，不是做文章，不是绘画" + RESET)
    print(RED + "画像，而是要打倒一切牛鬼蛇神。" + RESET)
    print(RED + "                                      (科学上网更快哦)" + RESET)
    print(RED + "=" * 50 + RESET)
    print()
    print("=" * 50)
    print("    Unity Asset Store 批量下载工具")
    print("=" * 50)
    print()


def check_python():
    """检查 Python 版本"""
    print(f"[OK] 已检测到 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()


def download_assets(headless=False):
    """下载资源"""
    clear_screen()
    # 选择浏览器
    print("请选择浏览器种类：")
    print("  [1] Microsoft Edge")
    print("  [2] Google Chrome")
    print("  [Enter] 使用内置 Chromium（需已安装 Playwright 浏览器）")
    browser_choice = input("请输入选项 (1/2，或直接回车): ").strip()
    if browser_choice == "1":
        browser_arg = ["--browser", "edge"]
    elif browser_choice == "2":
        browser_arg = ["--browser", "chrome"]
    else:
        browser_arg = []  # 默认保持原逻辑使用内置 chromium
    
    default_path = os.path.join(os.path.expanduser("~"), "Downloads", "UnityAssets")
    print()
    print("请输入下载保存路径（回车使用默认）：")
    print(f"默认: {default_path}")
    input_path = input("下载路径: ").strip()
    if input_path:
        expanded = os.path.expandvars(os.path.expanduser(input_path))
        download_path_arg = ["--download-path", expanded]
    else:
        download_path_arg = ["--download-path", default_path]

    if headless:
        print("正在启动下载（无头模式，不显示浏览器窗口）...")
        print()
        subprocess.run([sys.executable, "-u", "download_all_assets.py", "--headless", *browser_arg, *download_path_arg])
    else:
        print("正在启动下载（显示浏览器模式）...")
        print()
        subprocess.run([sys.executable, "-u", "download_all_assets.py", *browser_arg, *download_path_arg])
    input("\n按 Enter 键继续...")


def manage_assets():
    """管理资源"""
    clear_screen()
    print("正在启动资源管理器...")
    subprocess.run([sys.executable, "-u", "import_assets_to_unity.py"])
    input("\n按 Enter 键继续...")


def install_dependencies():
    """安装依赖"""
    clear_screen()
    print("正在安装依赖...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    env = os.environ.copy()
    env["PW_CFT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/chrome-for-testing"
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], env=env)
    if r.returncode != 0:
        print("\n[WARNING] 浏览器下载失败，可在下载时选择 Edge/Chrome，或稍后执行:")
        print("python -m playwright install chromium")
    print()
    print("[OK] 完成！")
    input("\n按 Enter 键继续...")


def show_help():
    """显示帮助"""
    clear_screen()
    print("=== 使用说明 ===")
    print()
    print("步骤 1: 选择选项 4 安装依赖")
    print("步骤 2: 选择选项 1 或 2 下载所有资源")
    print("       选项 2 = 无头模式（不显示浏览器窗口）")
    print("步骤 3: 资源将保存到:")
    print("   %USERPROFILE%/Downloads/UnityAssets/")
    print()
    print("如有问题，请参阅 README.md")
    print()
    input("按 Enter 键继续...")


def main():
    """主函数"""
    while True:
        clear_screen()
        print_header()
        print("请选择操作:")
        print()
        print("  [1] 下载我的所有资源（显示浏览器）")
        print("  [2] 下载我的所有资源（无头模式-不显示浏览器窗口）")
        print("  [3] 扫描并导入资源到 Unity")
        print("  [4] 安装依赖")
        print("  [5] 查看帮助")
        print("  [6] 退出")
        print()

        choice = input("请输入选项 (1-6): ").strip()

        if choice == "1":
            download_assets(headless=False)
        elif choice == "2":
            download_assets(headless=True)
        elif choice == "3":
            manage_assets()
        elif choice == "4":
            install_dependencies()
        elif choice == "5":
            show_help()
        elif choice == "6":
            print("\n感谢使用，再见！")
            sys.exit(0)
        else:
            print("\n[错误] 无效的选项，请重新输入")
            input("按 Enter 键继续...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n[错误] 发生错误: {e}")
        input("按 Enter 键退出...")
        sys.exit(1)
