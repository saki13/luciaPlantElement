# -*- coding: utf-8 -*-
"""
资源管线：把 AI / 外部生成的角色图，自动去背并规范化成动画框架可直接加载的精灵表。纯 Pillow。
两种输入：
  1) 单张图：python build_spritesheet.py 输入图.png 输出表.png
     —— “单立绘驱动”，所有格放同一标准姿态，动态交给 animation.py 的程序化变换。
  2) 帧目录：python build_spritesheet.py 帧目录 输出表.png
     —— 目录内按 idle_0.png/idle_1.png/walk_0.png.../hurt_1.png 命名，逐格去背拼表，
        每格是不同姿态；缺帧自动用 idle_0.png 兜底并告警。
去背针对白/近白背景（prompt 里要求纯白背景）；边缘双阈值羽化保留抗锯齿。
"""
import os
import sys
from PIL import Image

FRAME = 64
COLS, ROWS = 4, 4
ROW_NAMES = ["idle", "walk", "attack", "hurt"]
ROW_FRAMES = [2, 4, 3, 2]          # idle / walk / attack / hurt，与 animation.py 的 ANIM_DEF 对应
LO, HI = 12, 48                    # 到白色距离的去背双阈值（越小越激进）
FIT, BOTTOM_PAD = 56, 5            # 单图模式：角色最大边占 56px，底部留 5px 锚点
# 多帧目录模式：所有帧共用同一全局缩放，保证“同一角色身体等大、只变姿态”，不各自缩放导致帧间跳尺寸
MAX_W, MAX_H, DIR_BOTTOM_PAD = 62, 60, 4   # 格内可用宽/高与底部锚点留白


def remove_white_bg(im):
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            dist = max(255 - r, 255 - g, 255 - b)      # 纯白≈0；有色像素由最暗通道拉开
            if dist <= LO:
                na = 0
            elif dist >= HI:
                na = 255
            else:
                na = int((dist - LO) / (HI - LO) * 255)
            px[x, y] = (r, g, b, na)
    return im


def normalize_cell(im):
    """裁掉透明边 → 等比缩放到 FIT → 底部居中贴进 64x64 透明格。"""
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    scale = min(FIT / im.width, FIT / im.height)
    nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    cell = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
    cell.alpha_composite(im, ((FRAME - nw) // 2, FRAME - BOTTOM_PAD - nh))
    return cell


def cell_from_path(path):
    return normalize_cell(remove_white_bg(Image.open(path)))


def build_single(src, dst):
    cell = cell_from_path(src)
    sheet = Image.new("RGBA", (FRAME * COLS, FRAME * ROWS), (0, 0, 0, 0))
    for row, n in enumerate(ROW_FRAMES):
        for c in range(n):
            sheet.alpha_composite(cell, (c * FRAME, row * FRAME))
    sheet.save(dst)
    print("saved single-pose sheet:", dst, sheet.size, "from", src)


def crop_asset(path):
    """去背并裁到不透明 bbox，返回裁剪后的 RGBA（不缩放）。"""
    im = remove_white_bg(Image.open(path))
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def place_cell(im, scale):
    """用给定的全局 scale 等比缩放，再水平居中、底边对齐贴进 64x64 透明格。"""
    nw = max(1, round(im.width * scale))
    nh = max(1, round(im.height * scale))
    r = im.resize((nw, nh), Image.LANCZOS)
    cell = Image.new("RGBA", (FRAME, FRAME), (0, 0, 0, 0))
    cell.alpha_composite(r, ((FRAME - nw) // 2, FRAME - DIR_BOTTOM_PAD - nh))
    return cell


def count_content_bands(im, ink_thresh=40, min_gap_small=2, shrink=8, sig_ratio=0.10):
    """按行投影统计"互不相连的内容条带"数，用于发现模型返回的多姿态拼图。

    单角色应只有 1 个显著条带；4 个姿态竖排的拼图会得到 4~5 个。
    为提速先缩小 shrink 倍再判断；面积不足最大条带 sig_ratio 的碎条带（例如分离的
    脚下投影、frostbell 那种分段植物）不计入显著条带，减少误报。

    返回 (显著条带数, 全部条带数)。
    """
    a = im.getchannel("A")
    w, h = a.size
    sw, sh = max(1, w // shrink), max(1, h // shrink)
    small = a.resize((sw, sh), Image.BILINEAR)
    px = small.load()
    has_ink = [any(px[x, y] > ink_thresh for x in range(sw)) for y in range(sh)]

    bands = []
    y = 0
    while y < sh:
        if not has_ink[y]:
            y += 1
            continue
        y0 = y
        gap = 0
        while y < sh and gap <= min_gap_small:
            gap = 0 if has_ink[y] else gap + 1
            y += 1
        # y - gap 指向最后一个有墨迹行的下一行，减 1 才是闭区间末端；再夹到图内
        bands.append((y0, min(max(y0, y - gap - 1), sh - 1)))
    if not bands:
        return 0, 0

    mask = small.point(lambda v: 255 if v > ink_thresh else 0)
    mp = mask.load()
    areas = [sum(1 for yy in range(b0, b1 + 1) for xx in range(sw) if mp[xx, yy])
             for b0, b1 in bands]
    biggest = max(areas) or 1
    sig = sum(1 for area in areas if area >= biggest * sig_ratio)
    return sig, len(bands)


def build_dir(src_dir, dst):
    fallback = os.path.join(src_dir, "idle_0.png")
    if not os.path.exists(fallback):
        sys.exit(f"帧目录缺少基准帧 idle_0.png：{src_dir}")
    # 1) 解析每个槽位对应的文件路径（缺帧回退 idle_0）
    slots = []
    for row, name in enumerate(ROW_NAMES):
        for c in range(ROW_FRAMES[row]):
            p = os.path.join(src_dir, f"{name}_{c}.png")
            if not os.path.exists(p):
                print(f"  [warn] 缺帧 {name}_{c}.png，用 idle_0 兜底")
                p = fallback
            slots.append((row, c, p))
    # 2) 去背裁剪每个唯一文件，并计算让“最宽/最高帧”也能进格的全局统一缩放
    crops = {}
    scale = float("inf")
    for _, _, p in slots:
        if p not in crops:
            cr = crop_asset(p)
            crops[p] = cr
            scale = min(scale, MAX_W / cr.width, MAX_H / cr.height)
    # 2.5) 多角色帧自检：一帧里若存在多个面积相当的条带，说明模型返回了拼图，
    #      而下面的全局 scale 会把整张表 11 格一起压扁（fast/giant 事故的成因）。
    multi = []
    for p, cr in crops.items():
        sig, total = count_content_bands(cr)
        if sig > 1:
            multi.append((os.path.basename(p), total, sig))
    if multi:
        print(f"  [warn] 检测到 {len(multi)} 帧含多个角色（拼图），拼出的表会明显偏小/变形：")
        for name, total, sig in multi[:6]:
            print(f"          {name}: 内容条带 {total} 个，显著 {sig} 个")
        print("  [warn] 请删除该单位的 base.png 与 frames/，换掉 base_desc 里的"
              "相对比较措辞后重新生成")
    print(f"  global scale={scale:.4f} across {len(crops)} unique frames")
    # 3) 用同一缩放、同一底部锚点拼表，保证身体不跳尺寸、着地点一致
    sheet = Image.new("RGBA", (FRAME * COLS, FRAME * ROWS), (0, 0, 0, 0))
    for row, c, p in slots:
        sheet.alpha_composite(place_cell(crops[p], scale), (c * FRAME, row * FRAME))
    sheet.save(dst)
    print("saved multi-frame sheet:", dst, sheet.size, "from dir", src_dir)


def main(src, dst):
    if os.path.isdir(src):
        build_dir(src, dst)
    else:
        build_single(src, dst)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python build_spritesheet.py 输入图.png或帧目录 输出表.png")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
