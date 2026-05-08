#!/usr/bin/env python3
"""
UU韩漫 (uutoonman.com) 批量下载脚本
用法:
  # 下载整部漫画（从目录页）
  python3 download_images.py <URL>

  # 下载单章节
  python3 download_images.py <URL>

  # 指定起始章节（跳过前面的）
  python3 download_images.py <URL> --start 第10話

  # 指定输出目录
  python3 download_images.py <URL> -o /tmp/manga

  # 仅解析章节列表，不下载
  python3 download_images.py <URL> --list-only

  # 并行下载（默认8线程/章，2章同时）
  python3 download_images.py <URL>

  # 高速模式：4章同时，每章4线程
  python3 download_images.py <URL> -c 4 -w 4

  # 串行下载（兼容旧模式）
  python3 download_images.py <URL> -c 1 -w 1

  # 通过 list.txt 批量下载多部漫画
  python3 download_images.py --list list.txt

  # list.txt 格式示例（每行一个 URL，# 开头为注释，空行忽略）:
  # https://www.uutoonman.com/manhua/12345.html
  # https://www.uutoonman.com/manhua/67890.html
"""

import argparse
import concurrent.futures
import os
import re
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import List, Dict

# ── 全局配置 ──────────────────────────────────────────────
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_images")
DELAY_PER_IMAGE = 0.3        # 每张图片间隔（秒，串行模式，可通过 --delay 覆盖）
DELAY_PER_CHAPTER = 1.0      # 每章间隔（秒）
MAX_CONSECUTIVE_404 = 5      # 连续404停止阈值（仅探测模式生效）
REQUEST_TIMEOUT = 15         # 请求超时（秒）
MAX_RETRY = 3                # 单张图片重试次数
IMAGE_PAD_WIDTH = 3          # 文件名编号位数 (001, 002, ...)
DEFAULT_WORKERS = 8          # 每章并行下载线程数
DEFAULT_CHAPTER_WORKERS = 4  # 同时下载的章节数
RETRY_BACKOFF = [1, 2, 4]    # 重试退避间隔（秒），对应第1/2/3次重试
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}  # 可重试的HTTP状态码
RETRY_PASS_MAX = 3           # 失败图片补漏轮次
RETRY_PASS_DELAY = 5         # 补漏轮次间等待（秒）
PROBE_BEYOND_COUNT = 10      # 超出已知图片数的探测余量

# ── SSL ───────────────────────────────────────────────────
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


# ═══════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════

def extract_domain(url: str) -> str:
    """从 URL 提取协议+域名"""
    m = re.match(r'(https?://[^/]+)', url)
    return m.group(1) if m else "https://www.uutoonman.com"


def fetch_html(url: str) -> str:
    """获取网页 HTML 内容（分块读取，防止 chunked transfer 挂死）"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=REQUEST_TIMEOUT) as resp:
        chunks = []
        while True:
            try:
                chunk = resp.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)
            except Exception:
                break
        return b"".join(chunks).decode("utf-8", errors="ignore")


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip('. ')


def parse_manga_id(url: str) -> str:
    """从 URL 提取漫画 ID"""
    m = re.search(r'/manhua/(\d+)(?:\.html)?', url)
    if m:
        return m.group(1)
    raise ValueError(f"无法从 URL 提取漫画 ID: {url}")


def parse_chapter_id(url: str) -> str:
    """从 URL 提取章节 ID"""
    m = re.search(r'/capter/(\d+)', url)
    if m:
        return m.group(1)
    return None


# ═══════════════════════════════════════════════════════════
#  目录页解析
# ═══════════════════════════════════════════════════════════

def fetch_chapter_list(manga_url: str) -> tuple:
    """
    从漫画目录页解析章节列表和漫画名。
    支持 uutoonman.com / toptonmanhua.com 等多种站点结构。
    返回: (chapters, manga_name)
      chapters: [{"id": "46133", "title": "第1話", "image_count": 205}, ...]
      manga_name: str
    """
    html = fetch_html(manga_url)
    domain = extract_domain(manga_url)

    # ── 模式A: uutoonman.com 的 weui-cell 结构 ──
    pattern = (
        r'href="/manhua/capter/(\d+)">\s*'
        r'<div class="weui-cell__bd">\s*'
        r'<p>([^<]+)</p>\s*'
        r'</div>\s*'
        r'<div class="weui-cell__ft[^"]*">\s*'
        r'共\s*(\d+)\s*图'
    )
    matches = re.findall(pattern, html)

    # ── 模式B: toptonmanhua.com 的 list-item 结构 ──
    if not matches:
        pattern_b = (
            r'<li class="list-item">\s*'
            r'<a href="/manhua/capter/(\d+)"[^>]*'
            r'title="([^"]*)"[^>]*>\s*'
            r'(?:<span[^>]*>[^<]*</span>)?'
            r'([^<]+)</a>\s*'
            r'</li>'
        )
        matches_b = re.findall(pattern_b, html)
        if matches_b:
            # (ch_id, title_attr, link_text) -> 使用 link_text，图片数未知
            matches = [(ch_id, link_text.strip(), "0")
                      for ch_id, title_attr, link_text in matches_b]

    if not matches:
        # 备用模式：仅提取链接
        links = re.findall(r'href="/manhua/capter/(\d+)"', html)
        matches = [(lid, f"chapter_{lid}", "0") for lid in links]

    chapters = []
    for ch_id, title, count in matches:
        chapters.append({
            "id": ch_id,
            "title": sanitize_filename(title),
            "image_count": int(count),
            "url": f"{domain}/manhua/capter/{ch_id}",
        })

    # 提取漫画名 - 支持多种标题格式
    manga_name = "unknown"
    name_match = re.search(r'<title>([^<]+)</title>', html)
    if name_match:
        title_text = name_match.group(1).strip()
        # 格式1: "XXX漫画第Y話..." (uutoonman)
        m1 = re.search(r'^(.+?)漫画第', title_text)
        if m1:
            manga_name = m1.group(1).strip()
        else:
            # 格式2: "XXX漫画在线观看..." (uutoonman 目录页)
            m2 = re.search(r'^(.+?)漫画在线', title_text)
            if m2:
                manga_name = m2.group(1).strip()
            else:
                # 格式3: "漫画XXX在线免费观看..." (toptoonmanhua)
                m3 = re.search(r'^漫画(.+?)在线', title_text)
                if m3:
                    manga_name = m3.group(1).strip()
                else:
                    # 格式4: 兜底-取"漫画"和"-"之间的内容
                    m4 = re.search(r'^漫画(.+?)-', title_text)
                    if m4:
                        manga_name = m4.group(1).strip()
                    else:
                        # 格式5: 兜底-取"漫画"之前的内容
                        m5 = re.search(r'^(.+?)漫画', title_text)
                        if m5:
                            manga_name = m5.group(1).strip()

    manga_name = sanitize_filename(manga_name)
    return chapters, manga_name


def fetch_chapter_detail(chapter_url: str) -> dict:
    """
    从章节页解析标题和图片信息（用于单章节下载）。
    支持 uutoonman.com / toptonmanhua.com 等多种站点结构。
    """
    html = fetch_html(chapter_url)
    ch_id = parse_chapter_id(chapter_url)

    # 提取漫画 ID
    manga_id_match = re.search(r'img\.uumanhua\.xyz/bookimages/(\d+)/', html)
    manga_id = manga_id_match.group(1) if manga_id_match else None

    # 从 <title> 提取漫画名和章节名
    title_match = re.search(r'<title>([^<]+)</title>', html)
    title_text = title_match.group(1) if title_match else ""

    # 提取漫画名 - 支持多种格式
    manga_name = None
    # 格式1: "XXX漫画第Y話..." (uutoonman)
    m1 = re.search(r'^(.+?)漫画第', title_text)
    if m1:
        manga_name = sanitize_filename(m1.group(1).strip())
    else:
        # 格式2: "XXX漫画在线观看..." (uutoonman 目录页)
        m2 = re.search(r'^(.+?)漫画在线', title_text)
        if m2:
            manga_name = sanitize_filename(m2.group(1).strip())
        else:
            # 格式3: "漫画XXX第Y話..." (toptoonmanhua)
            m3 = re.search(r'^漫画(.+?)第', title_text)
            if m3:
                manga_name = sanitize_filename(m3.group(1).strip())
            else:
                # 格式4: 兜底-取"漫画"之前的内容
                m4 = re.search(r'^(.+?)漫画', title_text)
                if m4:
                    manga_name = sanitize_filename(m4.group(1).strip())

    # 提取章节标题
    # 格式A: "XXX漫画第Y話在线观看..."
    ch_title_match = re.search(r'漫画(第\d+話[^在线]*?)在线观看', title_text)
    if ch_title_match:
        title = sanitize_filename(ch_title_match.group(1).strip())
    else:
        # 备用1: 从 weui-cell 提取（目录页结构）
        weui_match = re.search(r'<div class="weui-cell__bd">\s*<p>([^<]+)</p>', html)
        if weui_match:
            title = sanitize_filename(weui_match.group(1))
        else:
            # 备用2: 从 title 提取非标准格式
            alt_match = re.search(r'漫画([^在线]+?)在线观看', title_text)
            title = sanitize_filename(alt_match.group(1).strip()) if alt_match else f"chapter_{ch_id}"

    # 提取图片数量
    count_match = re.search(r'共\s*(\d+)\s*图', html)
    image_count = int(count_match.group(1)) if count_match else 0

    # 如果没找到图片数量，从页面中的 img 标签计数
    if image_count == 0:
        imgs = re.findall(r'img\.uumanhua\.xyz/bookimages/\d+/\d+/\d+\.webp', html)
        image_count = len(imgs)

    return {
        "id": ch_id,
        "title": title,
        "image_count": image_count,
        "url": chapter_url,
        "manga_id": manga_id,
        "manga_name": manga_name,
    }


# ═══════════════════════════════════════════════════════════
#  图片下载
# ═══════════════════════════════════════════════════════════

def download_image(url: str, filepath: str, extra_retry: int = 0) -> str:
    """下载单张图片，返回结果类型。
    返回: "ok" | "404" | "failed"
    extra_retry: 额外重试次数（用于补漏轮次）
    """
    total_attempts = MAX_RETRY + 1 + extra_retry
    for attempt in range(total_attempts):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=REQUEST_TIMEOUT) as resp:
                data = resp.read()
                # 验证文件是否有效（非空且非HTML错误页）
                if len(data) < 50 or b'<html' in data[:200].lower():
                    return "failed"
                with open(filepath, "wb") as f:
                    f.write(data)
                return "ok"
        except urllib.error.HTTPError as e:
            # 404 = 文件不存在，不重试
            if e.code == 404:
                return "404"
            if e.code in RETRYABLE_HTTP_CODES and attempt < total_attempts - 1:
                backoff = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                print(f"    [RETRY] {os.path.basename(filepath)} HTTP {e.code}, {backoff}s后重试({attempt+1}/{total_attempts})")
                time.sleep(backoff)
                continue
            # 其他HTTP错误（如403），也尝试重试
            if attempt < total_attempts - 1:
                backoff = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                time.sleep(backoff)
                continue
            print(f"    [ERR] {os.path.basename(filepath)} - HTTP {e.code}")
            return "failed"
        except Exception as e:
            if attempt < total_attempts - 1:
                backoff = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
                time.sleep(backoff)
            else:
                print(f"    [ERR] {os.path.basename(filepath)} - {e}")
                return "failed"
    return "failed"


def _download_one_image(i: int, manga_id: str, chapter_id: str, ch_dir: str) -> tuple:
    """下载单张图片的线程任务，返回 (序号, 结果, 文件路径[, URL])
    结果: "downloaded" | "skipped" | "404" | "failed"
    """
    filename = f"{i:0{IMAGE_PAD_WIDTH}d}.webp"
    filepath = os.path.join(ch_dir, filename)
    url = f"https://img.uumanhua.xyz/bookimages/{manga_id}/{chapter_id}/{i}.webp"

    # 跳过已下载的文件
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return (i, "skipped", filepath)

    result = download_image(url, filepath)
    if result == "ok":
        return (i, "downloaded", filepath)
    else:
        # 清理下载失败的空/损坏文件
        if os.path.exists(filepath):
            os.remove(filepath)
        return (i, result, filepath, url)  # result is "404" or "failed"


def _retry_failed_images(failed_list: list, ch_dir: str, workers: int) -> int:
    """对失败图片进行补漏重试，返回补救成功的数量"""
    if not failed_list:
        return 0

    recovered = 0
    # 补漏用更少线程 + 额外重试次数，降低并发压力
    retry_workers = max(1, workers // 2)

    def _retry_one(item):
        i, filepath, url = item
        result = download_image(url, filepath, extra_retry=2)
        if result == "ok":
            return (i, True, filepath)
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
            return (i, False, filepath)

    with concurrent.futures.ThreadPoolExecutor(max_workers=retry_workers) as executor:
        futures = {executor.submit(_retry_one, item): item for item in failed_list}
        for future in concurrent.futures.as_completed(futures):
            try:
                idx, success, filepath = future.result()
                filename = os.path.basename(filepath)
                if success:
                    recovered += 1
                    size = os.path.getsize(filepath)
                    print(f"    [RECOVER] {filename} ({size:,} bytes)")
                else:
                    print(f"    [FAIL] {filename}")
            except Exception:
                pass

    return recovered


def download_chapter(manga_id: str, chapter: dict, output_base: str,
                     delay: float = DELAY_PER_IMAGE, workers: int = 1,
                     verbose: bool = True) -> dict:
    """
    下载单个章节的所有图片。支持并行下载。
    verbose: 是否输出逐图日志（多章节并行时建议 False）
    返回: {"downloaded": int, "skipped": int, "failed": int, "actual_files": int}
    """
    ch_dir = os.path.join(output_base, chapter["title"])
    os.makedirs(ch_dir, exist_ok=True)

    image_count = chapter["image_count"]
    is_probing = image_count == 0  # 未知图片数量，需要探测
    if is_probing:
        image_count = 500  # 未知数量时设置上限

    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    not_found_count = 0  # 404不计入failed（图片确实不存在）

    # ── 串行模式（workers=1）──────────────────────────────
    if workers <= 1:
        consecutive_404 = 0
        for i in range(1, image_count + 1):
            filename = f"{i:0{IMAGE_PAD_WIDTH}d}.webp"
            filepath = os.path.join(ch_dir, filename)
            url = f"https://img.uumanhua.xyz/bookimages/{manga_id}/{chapter['id']}/{i}.webp"

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                stats["skipped"] += 1
                consecutive_404 = 0
                continue

            result = download_image(url, filepath)
            if result == "ok":
                stats["downloaded"] += 1
                consecutive_404 = 0
                if verbose:
                    size = os.path.getsize(filepath)
                    print(f"    [OK] {filename} ({size:,} bytes)")
            elif result == "404":
                not_found_count += 1
                consecutive_404 += 1
                if verbose:
                    print(f"    [404] {filename}")
                # 仅探测模式下提前终止，且仅基于连续真实404
                if is_probing and consecutive_404 >= MAX_CONSECUTIVE_404:
                    if verbose:
                        print(f"    [INFO] 连续{consecutive_404}张404，探测终止")
                    break
            else:  # "failed" — 瞬态失败，不中断404计数
                stats["failed"] += 1
                consecutive_404 = 0
                if verbose:
                    print(f"    [SKIP] {filename}")
                if os.path.exists(filepath):
                    os.remove(filepath)

            time.sleep(delay)

    # ── 并行模式（workers>1）──────────────────────────────
    else:
        lock = threading.Lock()
        batch_size = workers * 4  # 每批提交的任务数

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for batch_start in range(1, image_count + 1, batch_size):
                batch_end = min(batch_start + batch_size, image_count + 1)
                indices = list(range(batch_start, batch_end))

                future_to_idx = {
                    executor.submit(_download_one_image, i, manga_id, chapter['id'], ch_dir): i
                    for i in indices
                }

                batch_404_count = 0
                batch_total = len(indices)

                for future in concurrent.futures.as_completed(future_to_idx):
                    try:
                        result_tuple = future.result()
                    except Exception:
                        with lock:
                            stats["failed"] += 1
                        continue

                    idx = result_tuple[0]
                    result = result_tuple[1]
                    filepath = result_tuple[2]
                    filename = os.path.basename(filepath)

                    with lock:
                        if result == "downloaded":
                            stats["downloaded"] += 1
                            if verbose:
                                size = os.path.getsize(filepath)
                                print(f"    [OK] {filename} ({size:,} bytes)")
                        elif result == "skipped":
                            stats["skipped"] += 1
                        elif result == "404":
                            not_found_count += 1
                            batch_404_count += 1
                            if verbose:
                                print(f"    [404] {filename}")
                        elif result == "failed":
                            stats["failed"] += 1
                            if verbose:
                                print(f"    [SKIP] {filename}")

                # 探测模式：整批全部404则提前终止
                if is_probing and batch_total > 0 and batch_404_count >= batch_total:
                    if verbose:
                        print(f"    [INFO] 批次全部404，探测终止")
                    break

    # ── 超出已知数量探测 ──────────────────────────────────
    if not is_probing and PROBE_BEYOND_COUNT > 0:
        # 找到当前最大序号
        existing_max = 0
        for f in os.listdir(ch_dir):
            if f.endswith('.webp'):
                try:
                    idx = int(f.split('.')[0])
                    if idx > existing_max:
                        existing_max = idx
                except ValueError:
                    pass
        # 如果已有数量达到预期，尝试探测更多图片
        if existing_max >= image_count:
            probe_start = image_count + 1
            probe_end = image_count + PROBE_BEYOND_COUNT + 1
            probe_found = 0
            consecutive_probe_404 = 0
            for i in range(probe_start, probe_end):
                filename = f"{i:0{IMAGE_PAD_WIDTH}d}.webp"
                filepath = os.path.join(ch_dir, filename)
                url = f"https://img.uumanhua.xyz/bookimages/{manga_id}/{chapter['id']}/{i}.webp"
                result = download_image(url, filepath)
                if result == "ok":
                    probe_found += 1
                    consecutive_probe_404 = 0
                    stats["downloaded"] += 1
                    if verbose:
                        size = os.path.getsize(filepath)
                        print(f"    [OK+] {filename} ({size:,} bytes) [额外探测]")
                elif result == "404":
                    consecutive_probe_404 += 1
                    if consecutive_probe_404 >= MAX_CONSECUTIVE_404:
                        break
                else:
                    consecutive_probe_404 = 0
                time.sleep(delay)
            if probe_found > 0:
                print(f"    [INFO] 探测发现 {probe_found} 张额外图片（超出目录标注的 {image_count} 张）")

    # ── 缺失图片扫描 + 补漏 ──────────────────────────────
    # 确定扫描范围：已知数量检查到 max(预期, 实际最大)；探测模式检查到已下载的最大序号
    existing_max = 0
    for f in os.listdir(ch_dir):
        if f.endswith('.webp'):
            try:
                idx = int(f.split('.')[0])
                if idx > existing_max:
                    existing_max = idx
            except ValueError:
                pass

    if not is_probing:
        scan_end = max(image_count, existing_max)
    else:
        scan_end = existing_max

    # 扫描缺失文件（覆盖所有未成功下载的图片，包括从未尝试的）
    failed_images = []
    for i in range(1, scan_end + 1):
        filename = f"{i:0{IMAGE_PAD_WIDTH}d}.webp"
        filepath = os.path.join(ch_dir, filename)
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            url = f"https://img.uumanhua.xyz/bookimages/{manga_id}/{chapter['id']}/{i}.webp"
            failed_images.append((i, filepath, url))

    if failed_images and RETRY_PASS_MAX > 0:
        consecutive_zero = 0  # 连续0救回轮次计数
        for retry_round in range(1, RETRY_PASS_MAX + 1):
            if not failed_images:
                break
            # 连续两轮都没救回来才放弃（网络抖动可能需要多等几轮）
            if consecutive_zero >= 2:
                break
            # 本轮等待：救回0时加倍等待，给网络更多恢复时间
            wait = RETRY_PASS_DELAY * (consecutive_zero + 1)
            if verbose:
                print(f"    [补漏第{retry_round}轮] 重试 {len(failed_images)} 张缺失图片（等待{wait}s）...")
            else:
                print(f"    [{chapter['title']}] 补漏第{retry_round}轮: {len(failed_images)} 张（等待{wait}s）")
            time.sleep(wait)
            recovered = _retry_failed_images(failed_images, ch_dir, workers)
            stats["downloaded"] += recovered
            stats["failed"] = max(0, stats["failed"] - recovered)
            # 更新剩余失败列表
            remaining = []
            for i, filepath, url in failed_images:
                if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                    remaining.append((i, filepath, url))
            failed_images = remaining
            if recovered == 0:
                consecutive_zero += 1
            else:
                consecutive_zero = 0  # 有救回则重置连续计数

    # 最终统计
    actual_files = len([f for f in os.listdir(ch_dir)
                       if f.endswith('.webp') and os.path.getsize(os.path.join(ch_dir, f)) > 0])
    stats["actual_files"] = actual_files

    # 将补漏后仍缺失的图片数补入 failed（修正"失败0但有缺失"的统计偏差）
    if failed_images:
        stats["failed"] = max(stats["failed"], len(failed_images))

    # 已知数量时报告缺失
    if not is_probing and chapter["image_count"] > 0 and actual_files < chapter["image_count"]:
        missing = chapter["image_count"] - actual_files
        print(f"    [WARN] 预期 {chapter['image_count']} 张，实际 {actual_files} 张，缺失 {missing} 张")

    return stats


# ═══════════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════════

def download_manga(url: str, args) -> bool:
    """
    下载单部漫画的主逻辑。
    返回 True 表示成功，False 表示失败（用于批量模式统计）。
    """
    delay = args.delay
    workers = max(1, args.workers)
    chapter_workers = max(1, args.chapter_workers)

    # ── 判断 URL 类型 ─────────────────────────────────────
    if "/capter/" in url:
        # 单章节下载
        print(f"[INFO] 检测到章节页 URL，解析章节信息...")
        chapter = fetch_chapter_detail(url)
        manga_id = chapter.get("manga_id") or parse_manga_id(url)
        chapters = [chapter]
        manga_name = chapter.get("manga_name") or f"manga_{manga_id}"
    else:
        # 目录页下载
        print(f"[INFO] 检测到目录页 URL，解析章节列表...")
        manga_id = parse_manga_id(url)
        chapters, manga_name = fetch_chapter_list(url)

    print(f"[INFO] 漫画: {manga_name}, 共 {len(chapters)} 个章节, 章节并行: {chapter_workers}, 每章线程: {workers}, 总并发: {chapter_workers * workers}")

    # ── 起始章节过滤 ─────────────────────────────────────
    if args.start:
        start_idx = None
        for idx, ch in enumerate(chapters):
            if args.start in ch["title"]:
                start_idx = idx
                break
        if start_idx is not None:
            chapters = chapters[start_idx:]
            print(f"[INFO] 从「{args.start}」开始，共 {len(chapters)} 个章节")
        else:
            print(f"[WARN] 未找到起始章节「{args.start}」，下载全部")

    # ── 仅列出章节 ────────────────────────────────────────
    if args.list_only:
        print(f"\n{'序号':>4}  {'章节ID':<8}  {'标题':<30}  {'图片数':>6}")
        print("-" * 60)
        for idx, ch in enumerate(chapters, 1):
            print(f"{idx:>4}  {ch['id']:<8}  {ch['title']:<30}  {ch['image_count']:>6}")
        print(f"\n共 {len(chapters)} 个章节")
        return True

    # ── 创建输出目录 ──────────────────────────────────────
    output_base = os.path.join(args.output, manga_name)
    os.makedirs(output_base, exist_ok=True)
    print(f"[INFO] 输出目录: {output_base}\n")

    # ── 下载 ──────────────────────────────────────────────
    total_downloaded = 0
    total_skipped = 0
    total_failed = 0
    start_time = time.time()

    if chapter_workers <= 1 or len(chapters) <= 1:
        # ── 逐章下载（原模式）──────────────────────────────
        for idx, ch in enumerate(chapters, 1):
            print(f"[{idx}/{len(chapters)}] 📖 {ch['title']} (ID: {ch['id']}, 预计 {ch['image_count']} 图)")

            stats = download_chapter(manga_id, ch, output_base, delay=delay, workers=workers)
            total_downloaded += stats["downloaded"]
            total_skipped += stats["skipped"]
            total_failed += stats["failed"]

            print(f"    → 下载 {stats['downloaded']}, 跳过 {stats['skipped']}, 失败 {stats['failed']}, "
                  f"实际文件 {stats.get('actual_files', '?')}")

            if idx < len(chapters):
                time.sleep(DELAY_PER_CHAPTER)

    else:
        # ── 多章节并行下载 ──────────────────────────────────
        print_lock = threading.Lock()
        completed_count = [0]  # 用列表以便在闭包中修改

        def _download_chapter_task(idx, ch):
            ch_title = ch['title']
            with print_lock:
                print(f"[{idx}/{len(chapters)}] 📖 {ch_title} 开始下载 (预计 {ch['image_count']} 图)")

            stats = download_chapter(manga_id, ch, output_base, delay=delay,
                                    workers=workers, verbose=False)

            with print_lock:
                completed_count[0] += 1
                print(f"[{completed_count[0]}/{len(chapters)}] ✅ {ch_title} → "
                      f"下载 {stats['downloaded']}, 跳过 {stats['skipped']}, "
                      f"失败 {stats['failed']}, 实际文件 {stats.get('actual_files', '?')}")
            return stats

        with concurrent.futures.ThreadPoolExecutor(max_workers=chapter_workers) as executor:
            future_to_ch = {
                executor.submit(_download_chapter_task, idx, ch): ch
                for idx, ch in enumerate(chapters, 1)
            }
            for future in concurrent.futures.as_completed(future_to_ch):
                try:
                    stats = future.result()
                    total_downloaded += stats["downloaded"]
                    total_skipped += stats["skipped"]
                    total_failed += stats["failed"]
                except Exception as e:
                    ch = future_to_ch[future]
                    print(f"[ERR] 章节 {ch['title']} 下载异常: {e}")
                    total_failed += 1

    # ── 汇总 ──────────────────────────────────────────────
    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"下载完成！")
    print(f"  漫画: {manga_name}")
    print(f"  章节: {len(chapters)}")
    print(f"  新下载: {total_downloaded} 张")
    print(f"  已存在跳过: {total_skipped} 张")
    print(f"  失败: {total_failed} 张")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  保存到: {output_base}")

    return True


def read_url_list(path: str) -> List[str]:
    """
    从 list.txt 读取 URL 列表。
    支持 # 注释和空行过滤。
    """
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def main():
    parser = argparse.ArgumentParser(
        description="UU韩漫 (uutoonman.com) 批量下载脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", nargs="?", default=None, help="漫画目录页或章节页 URL")
    parser.add_argument("-l", "--list", dest="list_file", default=None,
                        help="包含多部漫画 URL 的列表文件（每行一个 URL，# 开头为注释）")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="输出根目录")
    parser.add_argument("--start", default=None, help="起始章节标题（包含该章节），如: 第10話")
    parser.add_argument("--list-only", action="store_true", help="仅列出章节，不下载")
    parser.add_argument("--delay", type=float, default=DELAY_PER_IMAGE, help="下载间隔秒数（串行模式生效）")
    parser.add_argument("-w", "--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"每章并行下载线程数（默认 {DEFAULT_WORKERS}，设为 1 则串行）")
    parser.add_argument("-c", "--chapter-workers", type=int, default=DEFAULT_CHAPTER_WORKERS,
                        help=f"同时下载的章节数（默认 {DEFAULT_CHAPTER_WORKERS}，设为 1 则逐章，总并发=c×w）")
    args = parser.parse_args()

    # ── 参数校验 ──────────────────────────────────────────
    if not args.url and not args.list_file:
        parser.error("请提供 URL 或使用 --list 指定列表文件")
    if args.url and args.list_file:
        parser.error("URL 和 --list 参数不能同时使用")

    # ── 单部下载 ──────────────────────────────────────────
    if args.url:
        url = args.url.rstrip("/")
        download_manga(url, args)
        return

    # ── 批量下载（list.txt 模式）───────────────────────────
    urls = read_url_list(args.list_file)
    if not urls:
        print(f"[ERR] 列表文件为空或不含有效 URL: {args.list_file}")
        sys.exit(1)

    print(f"[INFO] 从列表文件读取到 {len(urls)} 部漫画\n")

    success_count = 0
    fail_count = 0
    overall_start = time.time()

    for idx, url in enumerate(urls, 1):
        url = url.rstrip("/")
        print(f"\n{'#'*60}")
        print(f"# [{idx}/{len(urls)}] 开始下载: {url}")
        print(f"{'#'*60}\n")
        try:
            ok = download_manga(url, args)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"\n[ERR] 漫画下载异常: {e}")
            fail_count += 1

        # 部间间隔（最后一部不需要）
        if idx < len(urls):
            print(f"\n[INFO] 等待 {DELAY_PER_CHAPTER}s 后继续下一部...")
            time.sleep(DELAY_PER_CHAPTER)

    overall_elapsed = time.time() - overall_start
    print(f"\n{'='*60}")
    print(f"全部任务完成！")
    print(f"  总计: {len(urls)} 部")
    print(f"  成功: {success_count} 部")
    print(f"  失败: {fail_count} 部")
    print(f"  总耗时: {overall_elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
