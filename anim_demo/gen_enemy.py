# -*- coding: utf-8 -*-
"""
配置驱动的【原创怪物角色】多帧生成（魔搭千问：文生图立绘 + 图像编辑逐帧）。
与植物不同，怪物会移动，因此 walk(4) 是真正的蹒跚行走循环：
  idle(2)=原地站立眨眼；walk(4)=左右脚交替行走；attack(3)=啃咬/举盾/重击；hurt(2)=受击。
拼表复用 build_spritesheet.py（同样 4×4、行 idle/walk/attack/hurt、64px 格）。

风格硬约束：Q 版可爱、绝不血腥恐怖，灰绿/土褐/暖橙为主、避免大面积紫色，
与植物同一套粗描边卡通手游画风、纯白底。怪物为原创设计，不复刻任何现有游戏资产。

用法：
  python gen_enemy.py --enemy normal --base
  python gen_enemy.py --enemy all --frames
前提：环境变量 MODELSCOPE_TOKEN / MS_TOKEN。
"""
import os
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_image_qwen import generate

ENEMIES_ROOT = os.path.join(HERE, "assets", "enemies")

# 敌人会移动，需要完整 11 帧（idle_0 由 base 复制，其余 AI 生成，含真行走循环 walk_0..3）
REQUIRED_PNG = ["idle_0", "idle_1", "walk_0", "walk_1", "walk_2", "walk_3",
                "attack_0", "attack_1", "attack_2", "hurt_0", "hurt_1"]

TAIL = (
    "固定平视角度；画面中只有这一个角色；严格保持角色既有身体结构和它的标志性防具/道具不变，"
    "不额外长出设定之外的新器官、新武器或无关物体；底部姿态在每一帧保持一致、不伸出额外底座；"
    "纯白色干净背景(#FFFFFF)，2D 卡通 Q 版手游怪物精灵图标风格，造型圆润可爱、绝不血腥恐怖，"
    "粗深色描边、明快平涂加少量渐变，以灰绿/土褐/暖橙/金属灰为主、避免大面积紫色，"
    "全身完整居中、四周留白、无地面投影、无文字水印。"
)
EDIT_GUARD = (
    "以参考图中的怪物为唯一基准，画完全相同的那一只，严格保持它的肤色、体型比例、服装、防具道具、"
    "描边、五官和朝向基准不变；仅在不改变身份的前提下调整姿态、脚步、形变与表情："
)

# 怪物通用：站立/行走/受击；攻击按 attack_kind 选模板
COMMON_FRAMES = {
    "idle_1": "原地站立，身体非常轻微地上下起伏并眨一下眼，前伸的两只短胳膊轻轻晃了晃，神态呆滞放松。",
    "walk_0": "行走第1姿势：左脚向前迈出、身体轻微向左倾并略微下沉，两只前伸的胳膊随步伐小幅摆动，眼睛保持正圆。",
    "walk_1": "行走第2姿势：双脚并拢回正、身体轻微向上一提，重心略抬高，胳膊回到前方，眼睛正圆。",
    "walk_2": "行走第3姿势：右脚向前迈出、身体轻微向右倾并略微下沉，胳膊小幅反方向摆动，眼睛正圆。",
    "walk_3": "行走第4姿势：双脚再次并拢回正、身体上提，与第2姿势呼应构成可循环的蹒跚步伐，眼睛正圆。",
    "hurt_0": "受击猛地向后一仰、身体上缩，两只圆眼睛紧紧闭成向下弯的弧线，嘴巴张成小O形，像被弹了一下。",
    "hurt_1": "吃痛后向前晃回、脑袋微微一歪，眼睛仍眯着，短胳膊耷拉一点，呈现晃动回弹的瞬间。",
}

ATTACK_SETS = {
    "bite": {
        "attack_0": "啃咬蓄力：脑袋向前一探、嘴巴大大张开，身体微微后缩压低，短胳膊前伸，像要一口咬下去。",
        "attack_1": "用力啃咬：脑袋猛地朝前凑到最前、张开的嘴用力咬合（卡通式、没有血），身体前倾拉长，眼睛鼓起。",
        "attack_2": "啃咬回收：脑袋缩回、嘴巴闭上做咀嚼状，身体回正到站立姿态，表情恢复呆滞。",
    },
    "shield": {
        "attack_0": "格挡蓄力：把前臂的小木盾收到胸前、身体微微后缩下蹲，盾面泛光，眼神警惕。",
        "attack_1": "举盾顶撞：木盾朝前用力顶出、身体低着头顶在盾后向前冲撞，盾面完全挡在身前，嘴巴用力抿紧。",
        "attack_2": "收盾回位：木盾收回胸前、身体重新站直，回到稳步推进的姿态，表情放松。",
    },
    "slam": {
        "attack_0": "重击蓄力：粗壮的双臂高高抬起、身体向后展开下蹲，浓眉紧皱、眼睛睁大，像在积攒力气。",
        "attack_1": "重拳砸下：双臂带着力量朝前方猛砸而下、身体前倾，拳头带明显速度残影，嘴巴怒吼成O形（卡通不恐怖）。",
        "attack_2": "重击回收：双臂收回身侧、身体重新站直，怒气收敛，恢复沉稳的站立姿态。",
    },
}

ENEMIES = {
    "normal": {
        "cn": "普通僵尸", "attack_kind": "bite",
        "base_desc": (
            "一只原创 Q 版小怪物“普通僵尸”：圆脑袋、灰绿色皮肤，两只无神的正圆小眼睛和一张小嘴，"
            "身穿破旧的深绿色上衣和暗紫色裤子（紫色只占很小面积），两只短胳膊朝前平伸、小短腿并拢，"
            "神态呆萌迟缓，圆润可爱、毫不恐怖，正面直立。"
        ),
    },
    "fast": {
        "cn": "快速僵尸", "attack_kind": "bite",
        "base_desc": (
            "一只原创 Q 版小怪物“快速僵尸”：比普通僵尸更瘦小、身体明显前倾呈冲刺姿态，灰绿皮肤、"
            "头上系一条红色运动头带，身穿利落的暗红短袖和运动鞋，两只圆眼睛睁得圆圆的、神情急切，"
            "短胳膊弯曲做摆动姿势，整体给人马上要冲过来的速度感，圆润可爱不恐怖，正面直立。"
        ),
    },
    "banner": {
        "cn": "旗手僵尸", "attack_kind": "bite",
        "base_desc": (
            "一只原创 Q 版小怪物“旗手僵尸”：外形和普通僵尸相近的灰绿圆头小僵尸，穿深绿旧上衣，"
            "一只手高举一根细木杆、杆顶挂着一面略显破旧的小灰旗（旗子是它的标志道具），另一只胳膊前伸，"
            "眼睛圆睁、嘴巴像在喊号子，呆萌中带点一本正经，圆润可爱不恐怖，正面直立。"
        ),
    },
    "cone": {
        "cn": "路障僵尸", "attack_kind": "bite",
        "base_desc": (
            "一只原创 Q 版小怪物“路障僵尸”：灰绿圆头、穿深绿旧上衣的呆萌小僵尸，头顶倒扣一只橙白相间条纹的"
            "塑料交通锥当作简易头盔（轻甲），交通锥稳稳罩住头顶、露出下面两只圆眼睛和小嘴，短胳膊前伸、小短腿并拢，"
            "橙色是它最显眼的颜色，圆润可爱不恐怖，正面直立。"
        ),
    },
    "shield_cadet": {
        "cn": "格挡盾兵", "attack_kind": "shield",
        "base_desc": (
            "一只原创 Q 版小怪物“格挡盾兵”：灰绿色皮肤、身形端正的小僵尸，头戴简易护额和半脸面罩，"
            "两只前臂各绑着一面原木色小圆盾、盾面有金属包边和加固条纹（这是它格挡用的标志性防具），"
            "身穿深绿色短甲，眼睛沉稳、小嘴抿紧，像训练有素的前排小兵，短胳膊架盾在前，圆润可爱不恐怖，正面直立。"
        ),
    },
    "bucket": {
        "cn": "铁桶僵尸", "attack_kind": "bite",
        "base_desc": (
            "一只原创 Q 版小怪物“铁桶僵尸”：灰绿圆头小僵尸，头顶紧紧扣着一只银灰色金属水桶当厚重头盔（重甲），"
            "桶身有金属高光和两道竖向小缝、恰好露出下面两只圆眼睛，身穿深绿旧上衣、短胳膊前伸，"
            "金属灰是它的主色、显得比路障更扛打，造型笨重可爱、毫不恐怖，正面直立。"
        ),
    },
    "giant": {
        "cn": "巨人僵尸", "attack_kind": "slam",
        "base_desc": (
            "一只原创 Q 版大块头怪物“巨人僵尸”：身高体型明显比普通僵尸高大一圈、肩膀宽厚、圆鼓鼓的灰绿色身躯，"
            "浓眉下两只小眼睛、下巴敦实，身穿打补丁的褐色粗布衣，两条粗壮的手臂垂在身侧、拳头很大，小短腿撑住沉重身体，"
            "神态憨厚却充满压迫感，整体仍是圆润 Q 版比例、不血腥不恐怖，正面直立。"
        ),
    },
    "boss_50": {
        "cn": "五十轮统领·壁垒巨尸", "attack_kind": "slam",
        "base_desc": (
            "一只原创 Q 版 Boss 怪物“壁垒巨尸”：体型最大最魁梧的灰绿色巨尸，身披多层暗银色金属护甲片和厚重肩甲，"
            "两条前臂各绑一面带尖钉的厚重格挡护臂、胸前有金属护心甲，头戴尖顶战盔、战盔缝隙里透出沉稳的红橙色目光（不狰狞），"
            "褐色战衣、铆钉与甲片层次丰富，金属灰配暖橙、几乎不用紫色，像一座会移动的壁垒，统帅气场十足却保持 Q 版圆润、不恐怖，正面直立。"
        ),
    },
}


def paths(key):
    root = os.path.join(ENEMIES_ROOT, key)
    return root, os.path.join(root, "base.png"), os.path.join(root, "frames")


def make_base(key):
    cfg = ENEMIES[key]
    root, base, _ = paths(key)
    os.makedirs(root, exist_ok=True)
    if os.path.exists(base):
        print("skip base (exists):", key, base)
        return
    prompt = "2D 游戏怪物精灵立绘，" + cfg["base_desc"] + TAIL
    print("=== base立绘:", cfg["cn"], "===")
    generate(prompt, base)


def make_frames(key):
    cfg = ENEMIES[key]
    root, base, frames_dir = paths(key)
    if not os.path.exists(base):
        sys.exit(f"缺少标准立绘 {base}，请先运行：python gen_enemy.py --enemy {key} --base")
    os.makedirs(frames_dir, exist_ok=True)
    idle0 = os.path.join(frames_dir, "idle_0.png")
    if not os.path.exists(idle0):
        shutil.copyfile(base, idle0)
    frames = dict(COMMON_FRAMES)
    frames.update(ATTACK_SETS[cfg["attack_kind"]])
    failed = []
    for name, desc in frames.items():
        out = os.path.join(frames_dir, name + ".png")
        if os.path.exists(out):
            print("skip frame (exists):", key, name)
            continue
        print("=== frame:", cfg["cn"], name, "===")
        try:
            generate(EDIT_GUARD + desc + TAIL, out, ref_path=base)
        except SystemExit as e:
            failed.append((name, str(e)))
            print("!! frame failed:", name, e)
    print("\nDONE", key, "failed:", failed if failed else "none")
    print("下一步拼表：python build_spritesheet.py",
          os.path.relpath(frames_dir, HERE),
          os.path.join("assets", "sprites", "enemies", key + ".png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enemy", required=True, choices=list(ENEMIES) + ["all"])
    ap.add_argument("--base", action="store_true")
    ap.add_argument("--frames", action="store_true")
    a = ap.parse_args()
    if not (a.base or a.frames):
        ap.error("至少指定 --base 或 --frames")
    keys = list(ENEMIES) if a.enemy == "all" else [a.enemy]
    for k in keys:
        if a.base:
            make_base(k)
        if a.frames:
            make_frames(k)


if __name__ == "__main__":
    main()
