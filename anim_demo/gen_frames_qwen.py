# -*- coding: utf-8 -*-
"""
批量生成“同角色不同姿态”的序列帧（千问图像编辑），再交给 build_spritesheet.py 拼表。
- 所有帧都以同一张标准立绘为参考（星型锚定，不用上一帧链式生成），尽量抑制角色漂移。
- 已存在的帧自动跳过，失败不中断；重跑本脚本即可只补失败/不满意的帧。
前提：环境变量 MODELSCOPE_TOKEN / MS_TOKEN；参考立绘默认取 ../logs/qwen_test.png。
"""
import os
import sys
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gen_image_qwen import generate

REF = os.path.join(os.path.dirname(HERE), "logs", "qwen_test.png")
OUT_DIR = os.path.join(HERE, "assets", "frames_raw")

COMMON = (
    "以参考图中的角色为唯一基准，画完全相同的那一只绿色水滴史莱姆，严格保持：相同的翠绿色与果冻渐变、"
    "深绿色粗描边、两只正圆形纯黑小眼睛、浅绿椭圆高光、光滑的圆顶水滴外形；固定平视角度；画面中只有这一个角色，"
    "绝对不要长出手、脚、翅膀、角、尾巴、耳朵、武器等任何新器官或额外物体；纯白色干净背景，2D 卡通手游精灵图标风格，"
    "全身完整居中、四周留白、无地面投影、无文字水印。在以上前提下，仅把身体形状、倾斜挤压和眼嘴表情改成："
)
FRAMES = {
    "idle_1": "待机呼吸并轻轻眨眼：双眼都闭成短短的水平弧线，身体非常轻微地竖直压扁，姿态端正放松。",
    "walk_0": "向左蠕动：身体轻微向左前方倾斜并略横向压扁，底部果冻向左鼓起，眼睛保持正圆，循环第1姿势。",
    "walk_1": "蠕动上弹：身体回正并轻微竖直拉长、底部收窄、重心略向上，眼睛正圆，循环第2姿势。",
    "walk_2": "向右蠕动：身体轻微向右前方倾斜并略横向压扁，底部果冻向右鼓起，眼睛正圆，循环第3姿势。",
    "walk_3": "蠕动回位：身体回正并轻微拉长、重心略向前，与第2姿势呼应构成可循环动作，眼睛正圆，第4姿势。",
    "attack_0": "攻击蓄力：身体明显横向压扁、纵向缩短并稍向后缩，眼睛睁大，小嘴张成小O形，像在蓄力，保持光滑无四肢。",
    "attack_1": "向前扑击突刺：身体明显竖直拉长并微微前倾，小嘴张成O形用力，眼神朝前，有冲击动感，但不增加任何器官。",
    "attack_2": "攻击回收：身体从扑击恢复到接近端正站立、仍略前倾，嘴巴闭回微笑状，动作收尾。",
    "hurt_0": "受击后仰：身体猛地向后仰并略横向压扁，双眼紧闭成向下弯的弧线，小嘴张成O形，像被撞了一下。",
    "hurt_1": "受击摇晃：在后仰基础上微微回弹侧歪，眼睛仍闭着，呈现吃痛后晃动的瞬间。",
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    idle0 = os.path.join(OUT_DIR, "idle_0.png")
    if not os.path.exists(idle0):
        shutil.copyfile(REF, idle0)
        print("idle_0 使用标准立绘:", idle0)
    failed = []
    for name, desc in FRAMES.items():
        out = os.path.join(OUT_DIR, name + ".png")
        if os.path.exists(out):
            print("skip(already exists):", name)
            continue
        print("=== generating", name, "===")
        try:
            generate(COMMON + desc, out, ref_path=REF)
        except SystemExit as e:
            failed.append((name, str(e)))
            print("!! frame failed:", name, e)
    print("\nDONE. failed frames:", failed if failed else "none")


if __name__ == "__main__":
    main()
