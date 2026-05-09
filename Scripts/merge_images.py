#!/usr/bin/env python3
"""
漫画图片竖式拼接转 PDF 脚本

支持两种目录结构：
  1. 包含子目录（按子目录顺序拼接）: ./downloaded_images/报告女班长_一根突起
  2. 不包含子目录（直接按文件名排序）: ./downloaded_images/秘密教学

用法:
  # 单目录处理：输入目录，输出同名的 PDF 到父目录
  python3 merge_images.py ./downloaded_images/秘密教学

  # 指定输出路径
  python3 merge_images.py ./downloaded_images/秘密教学 -o ./output/秘密教学.pdf

  # 批量处理子目录：输入目录下的每个直接子目录各自生成一个 PDF
  python3 merge_images.py ./downloaded_images -c -w 4

  # 批量处理并指定输出目录
  python3 merge_images.py ./downloaded_images -c -o ./output/

  # 指定输出宽度（像素），不指定则按原图最大宽度自动适配
  python3 merge_images.py ./downloaded_images/秘密教学 --width 800

  # 指定每页最大高度（像素），默认 50000，0 表示不限制单页高度
  python3 merge_images.py ./downloaded_images/秘密教学 --page-height 30000

  # 指定并行工作进程数
  python3 merge_images.py ./downloaded_images/秘密教学 -w 4
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed

from PIL import Image

# 解除超大图片限制（拼接后的长图像素数可能很高）
Image.MAX_IMAGE_PIXELS = None

# 兼容旧版 PIL 的 resize 算法
try:
    RESAMPLE_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_FILTER = Image.LANCZOS  # Pillow < 9.1.0

# ── 全局配置 ──────────────────────────────────────────────
SUPPORTED_EXTS = ('.webp', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

# PDF 规范最大页面尺寸（points），1 point = 1/72 inch
# PDF 规范上限为 14400 x 14400 points = 200 x 200 inches
PDF_SPEC_MAX_POINTS = 14400

# 默认 PDF 输出分辨率（DPI）
PDF_RESOLUTION = 100.0

# 每页最大高度（像素）：根据 PDF 规范上限和 DPI 动态计算
# 在 100 DPI 下：14400 / 72 * 100 = 20000 px
# 在  72 DPI 下：14400 / 72 *  72 = 14400 px
DEFAULT_PAGE_HEIGHT = int(PDF_SPEC_MAX_POINTS / 72.0 * PDF_RESOLUTION)

MIN_FILE_SIZE = 2048           # 小于此字节数的图片视为异常小图，默认跳过


def _max_page_height_px(resolution=PDF_RESOLUTION):
    """根据 PDF 规范限制和分辨率，计算单页最大允许高度（像素）。"""
    return int(PDF_SPEC_MAX_POINTS / 72.0 * resolution)


def natural_sort_key(s):
    """自然排序 key，正确处理数字顺序（如 第1話, 第2話, 第10話）"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def collect_images(input_dir: str, min_size: int = MIN_FILE_SIZE):
    """
    收集目录下的图片并按顺序排列。

    规则：
      - 如果存在包含图片的直接子目录，按子目录名自然排序，
        每个子目录内的图片按文件名自然排序。
      - 否则，直接收集根目录下的图片并按文件名自然排序。

    返回: (image_paths: list[str], has_subdirs: bool)
    """
    subdirs_with_images = []
    direct_images = []

    for entry in os.listdir(input_dir):
        full_path = os.path.join(input_dir, entry)
        if os.path.isdir(full_path):
            # 检查该子目录中是否包含图片（仅检查一层）
            has_img = False
            try:
                for f in os.listdir(full_path):
                    if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS:
                        has_img = True
                        break
            except OSError:
                continue
            if has_img:
                subdirs_with_images.append(entry)
        else:
            ext = os.path.splitext(entry)[1].lower()
            if ext in SUPPORTED_EXTS:
                direct_images.append(entry)

    image_paths = []
    has_subdirs = False

    if subdirs_with_images:
        has_subdirs = True
        subdirs_with_images.sort(key=natural_sort_key)
        for subdir in subdirs_with_images:
            subdir_path = os.path.join(input_dir, subdir)
            files = []
            try:
                for f in os.listdir(subdir_path):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        fp = os.path.join(subdir_path, f)
                        try:
                            if os.path.getsize(fp) >= min_size:
                                files.append(f)
                        except OSError:
                            continue
            except OSError:
                continue
            files.sort(key=natural_sort_key)
            for f in files:
                image_paths.append(os.path.join(subdir_path, f))
    elif direct_images:
        direct_images.sort(key=natural_sort_key)
        for f in direct_images:
            fp = os.path.join(input_dir, f)
            try:
                if os.path.getsize(fp) >= min_size:
                    image_paths.append(fp)
            except OSError:
                continue

    return image_paths, has_subdirs


def create_page_pdf(page_images, final_width, output_path, show_progress=False):
    """
    将一组图片竖式拼接并保存为单页 PDF。

    page_images: list of (filepath, scaled_width, scaled_height)
    show_progress: 是否在终端打印拼接进度
    """
    total_height = sum(h for _, _, h in page_images)
    canvas = Image.new('RGB', (final_width, total_height), (255, 255, 255))
    y_offset = 0
    total = len(page_images)

    for i, (filepath, _, _) in enumerate(page_images, 1):
        if show_progress and (i == 1 or i == total or i % 200 == 0):
            print(f"  [{i}/{total}] 拼接中...")
        img = Image.open(filepath)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        if img.width != final_width:
            ratio = final_width / img.width
            new_h = int(img.height * ratio)
            img = img.resize((final_width, new_h), RESAMPLE_FILTER)

        x_offset = (final_width - img.width) // 2
        canvas.paste(img, (x_offset, y_offset))
        y_offset += img.height
        img.close()

    canvas.save(output_path, 'PDF', resolution=PDF_RESOLUTION)
    return output_path


def merge_pdfs(pdf_files, output_path):
    """
    使用 pypdf 或 PyPDF2 合并多个 PDF 文件。
    按 pdf_files 的顺序合并。
    """
    total = len(pdf_files)
    show_merge_progress = total > 10
    # 优先尝试新版 pypdf
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for i, pdf in enumerate(pdf_files, 1):
            if show_merge_progress and (i == 1 or i == total or i % 50 == 0):
                print(f"  [{i}/{total}] 合并页面...")
            writer.append(pdf)
        with open(output_path, 'wb') as f:
            writer.write(f)
        return
    except ImportError:
        pass

    # 回退到 PyPDF2
    try:
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        for i, pdf in enumerate(pdf_files, 1):
            if show_merge_progress and (i == 1 or i == total or i % 50 == 0):
                print(f"  [{i}/{total}] 合并页面...")
            merger.append(pdf)
        merger.write(output_path)
        merger.close()
        return
    except ImportError:
        pass

    raise ImportError(
        "缺少 PDF 合并依赖库。请安装其中一个：\n"
        "  pip install pypdf\n"
        "  或\n"
        "  pip install PyPDF2"
    )


def split_into_pages(images_info, page_max_height):
    """
    将图片列表按 page_max_height 分页。
    images_info: list of (filepath, width, height)
    返回: list of list of (filepath, width, height)
    """
    if page_max_height <= 0:
        return [images_info]

    pages = []
    current_page = []
    current_height = 0

    for info in images_info:
        _, _, h = info
        # 如果当前页非空，且添加该图会超出限制，则开新页
        if current_page and current_height + h > page_max_height:
            pages.append(current_page)
            current_page = [info]
            current_height = h
        else:
            current_page.append(info)
            current_height += h

    if current_page:
        pages.append(current_page)

    return pages


def build_pdf(input_dir: str, output_pdf: str, width: int = None,
              page_height: int = DEFAULT_PAGE_HEIGHT,
              min_size: int = MIN_FILE_SIZE,
              workers: int = 1) -> bool:
    """
    将单个目录下的图片拼接为单个 PDF。
    返回是否成功生成 PDF。
    """
    # 1. 收集图片
    image_paths, has_subdirs = collect_images(input_dir, min_size=min_size)
    if not image_paths:
        print(f"[WARN] 未找到任何有效图片: {input_dir}")
        return False

    print(f"[INFO] 输入目录: {input_dir}")
    print(f"[INFO] 发现 {len(image_paths)} 张图片")
    if has_subdirs:
        print(f"[INFO] 目录结构: 多子目录（章节）")
    else:
        print(f"[INFO] 目录结构: 单目录")
    print(f"[INFO] 输出: {output_pdf}")
    print(f"[INFO] 工作进程: {workers}")

    # 2. 预加载尺寸（低内存占用）
    print("正在读取图片尺寸...")
    images_info = []  # [(filepath, orig_w, orig_h), ...]
    max_width = 0
    skipped = 0
    total_images = len(image_paths)
    show_read_progress = total_images > 500
    for idx, fp in enumerate(image_paths, 1):
        if show_read_progress and (idx % 500 == 0 or idx == total_images):
            print(f"  [{idx}/{total_images}] 读取尺寸中...")
        try:
            with Image.open(fp) as img:
                w, h = img.size
                images_info.append((fp, w, h))
                if w > max_width:
                    max_width = w
        except Exception as e:
            print(f"  [WARN] 跳过 {os.path.relpath(fp, input_dir)}: {e}")
            skipped += 1

    if not images_info:
        print("[ERR] 没有成功加载任何图片")
        return False

    if skipped:
        print(f"  已跳过 {skipped} 张异常图片")

    # 3. 确定最终宽度并预计算缩放后高度
    final_width = width if width else max_width
    # 检查宽度是否超出 PDF 规范限制
    max_allowed_width = _max_page_height_px()  # 复用同一计算函数
    if final_width > max_allowed_width:
        print(f"[INFO] 宽度 {final_width}px 超出 PDF 规范上限 {max_allowed_width}px，已自动调整")
        final_width = max_allowed_width
    if width:
        print(f"[INFO] 统一缩放到宽度 {final_width}px...")
        images_info = [
            (fp, final_width, int(h * final_width / w))
            for fp, w, h in images_info
        ]
        print(f"[INFO] 缩放完成，共 {len(images_info)} 张")
    else:
        if any(w != max_width for _, w, _ in images_info):
            print(f"[INFO] 统一缩放到最大宽度 {max_width}px...")
            images_info = [
                (fp, max_width, int(h * max_width / w))
                for fp, w, h in images_info
            ]
            print(f"[INFO] 缩放完成，共 {len(images_info)} 张")
        else:
            # 无需缩放
            images_info = [(fp, w, h) for fp, w, h in images_info]

    # 4. 分页（强制不超过 PDF 规范最大页面尺寸）
    total_height = sum(h for _, _, h in images_info)
    max_allowed = _max_page_height_px()
    effective_page_height = page_height if page_height > 0 else max_allowed
    if effective_page_height > max_allowed:
        print(f"[INFO] 页高 {effective_page_height}px 超出 PDF 规范上限 {max_allowed}px，已自动调整")
        effective_page_height = max_allowed
    pages = split_into_pages(images_info, effective_page_height)
    print(f"[INFO] 总高度: {total_height}px，将输出 {len(pages)} 页")

    # 5. 生成各页 PDF
    temp_dir = tempfile.mkdtemp(prefix="merge_pdf_")
    temp_pdfs = []

    try:
        if workers <= 1 or len(pages) == 1:
            for idx, page in enumerate(pages, 1):
                print(f"  [{idx}/{len(pages)}] 生成页面（含 {len(page)} 张图）...")
                temp_path = os.path.join(temp_dir, f"page_{idx:04d}.pdf")
                create_page_pdf(page, final_width, temp_path, show_progress=True)
                temp_pdfs.append(temp_path)
        else:
            # 并行生成
            tasks = []
            for idx, page in enumerate(pages, 1):
                temp_path = os.path.join(temp_dir, f"page_{idx:04d}.pdf")
                tasks.append((idx, page, temp_path))

            with ProcessPoolExecutor(max_workers=workers) as executor:
                future_to_info = {}
                for idx, page, temp_path in tasks:
                    future = executor.submit(
                        create_page_pdf, page, final_width, temp_path
                    )
                    future_to_info[future] = (idx, temp_path)

                results = {}
                for future in as_completed(future_to_info):
                    idx, temp_path = future_to_info[future]
                    try:
                        future.result()
                        results[idx] = (temp_path, None)
                    except Exception as e:
                        results[idx] = (temp_path, str(e))

                for idx in sorted(results.keys()):
                    temp_path, error = results[idx]
                    if error:
                        print(f"  [{idx}/{len(pages)}] [ERR] 页面生成失败: {error}")
                        raise RuntimeError(f"第 {idx} 页生成失败: {error}")
                    print(f"  [{idx}/{len(pages)}] 生成页面...")
                    temp_pdfs.append(temp_path)

        # 6. 合并为最终 PDF
        print(f"[INFO] 正在合并 {len(temp_pdfs)} 页到 PDF...")
        merge_pdfs(temp_pdfs, output_pdf)
        size_mb = os.path.getsize(output_pdf) / (1024 * 1024)
        print(f"[OK] 已保存: {output_pdf} ({size_mb:.2f} MB)")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="将目录下的图片按顺序竖式拼接，输出为 PDF 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input_dir", help="包含图片的输入目录")
    parser.add_argument("-o", "--output", default=None,
                        help="输出路径（单目录模式为 PDF 文件路径；子目录模式为输出目录）")
    parser.add_argument("--width", type=int, default=None,
                        help="统一输出图片宽度（像素），不指定则按原图最大宽度自动适配")
    parser.add_argument("--page-height", type=int, default=DEFAULT_PAGE_HEIGHT,
                        help=f"每页最大高度（像素），超过则自动分页。0 表示不限制（单页），"
                             f"但会受 PDF 规范上限约束。默认: {DEFAULT_PAGE_HEIGHT}")
    parser.add_argument("--min-size", type=int, default=MIN_FILE_SIZE,
                        help=f"过滤小于此字节数的异常小图（默认: {MIN_FILE_SIZE}）")
    parser.add_argument("-w", "--workers", type=int,
                        default=min(os.cpu_count() or 1, 8),
                        help=f"并行工作进程数（默认: min(CPU核数, 8)）")
    parser.add_argument("-c", "--children", action="store_true",
                        help="将输入目录下的每个直接子目录分别处理为一个独立的 PDF")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    if not os.path.isdir(input_dir):
        print(f"[ERR] 输入目录不存在: {input_dir}")
        sys.exit(1)

    if args.children:
        # ── 子目录批量模式 ──────────────────────────────
        children = []
        for entry in os.listdir(input_dir):
            full_path = os.path.join(input_dir, entry)
            if os.path.isdir(full_path):
                paths, _ = collect_images(full_path, min_size=args.min_size)
                if paths:
                    children.append((entry, full_path))

        if not children:
            print(f"[WARN] 未找到任何包含图片的有效子目录: {input_dir}")
            sys.exit(0)

        print(f"[INFO] 发现 {len(children)} 个子目录待处理")

        # 确定输出目录
        if args.output:
            output_dir = os.path.abspath(args.output)
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = input_dir

        # 顺序或并行处理
        if args.workers <= 1 or len(children) == 1:
            total_children = len(children)
            for i, (name, path) in enumerate(children, 1):
                output_pdf = os.path.join(output_dir, f"{name}.pdf")
                print(f"\n{'='*50}")
                print(f"[{i}/{total_children}] 处理: {name}")
                print(f"{'='*50}")
                try:
                    build_pdf(path, output_pdf, width=args.width,
                              page_height=args.page_height, min_size=args.min_size,
                              workers=1)
                except Exception as e:
                    print(f"[ERR] {name} 处理失败: {e}")
        else:
            print(f"[INFO] 并行工作进程: {args.workers}")
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                future_to_name = {}
                for name, path in children:
                    output_pdf = os.path.join(output_dir, f"{name}.pdf")
                    future = executor.submit(
                        build_pdf, path, output_pdf,
                        width=args.width, page_height=args.page_height,
                        min_size=args.min_size, workers=1
                    )
                    future_to_name[future] = name

                for future in as_completed(future_to_name):
                    name = future_to_name[future]
                    try:
                        success = future.result()
                        if success:
                            print(f"[OK] {name} 处理完成")
                        else:
                            print(f"[WARN] {name} 无有效图片")
                    except Exception as e:
                        print(f"[ERR] {name} 处理失败: {e}")

        print(f"\n{'='*50}")
        print(f"批量处理完成！输出目录: {output_dir}")

    else:
        # ── 单目录模式 ──────────────────────────────
        if args.output:
            output_pdf = os.path.abspath(args.output)
            os.makedirs(os.path.dirname(output_pdf) or '.', exist_ok=True)
        else:
            parent_dir = os.path.dirname(input_dir)
            base_name = os.path.basename(input_dir)
            output_pdf = os.path.join(parent_dir, f"{base_name}.pdf")

        try:
            build_pdf(input_dir, output_pdf, width=args.width,
                      page_height=args.page_height, min_size=args.min_size,
                      workers=args.workers)
        except Exception as e:
            print(f"[ERR] 处理失败: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
