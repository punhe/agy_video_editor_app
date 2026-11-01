"""
caption_generator.py
Generates spicy, shadowban-safe X/Twitter captions for short-drama clips
following the guidelines in x-shortdrama-caption skill:
- 2-3 diverse hook styles (Question hook, Declarative tease, In-character quote)
- Rotated hashtag combinations (2-3 max)
- Engagement reply driver
- Suggestive teasing tone without trigger flags
- AGY CLI AI generation with smart offline rule-based fallback
"""

import os
import sys
import random
import subprocess
import shutil

# Hashtag pool for shadowban-avoidance rotation
HASHTAG_POOLS = [
    ["#shortdrama", "#romance", "#miniseries"],
    ["#AIdrama", "#darkromance", "#dramaseries"],
    ["#shortdrama", "#mafiaromance", "#mustwatch"],
    ["#miniseries", "#billionaireromance", "#drama"],
    ["#AIdrama", "#fantasyromance", "#spicyromance"],
    ["#shortdrama", "#forbiddenlove", "#reelsdrama"],
    ["#miniseries", "#secretromance", "#kdrama"],
    ["#shortdrama", "#tension", "#watchnow"]
]

CTA_POOLS = [
    "Full episode waiting in bio. 🍷",
    "Stream the uncut version in bio link. 🔥",
    "Watch what happens next via link in bio. 🫦",
    "Link in bio for the full story. 🖤",
    "Catch every secret in the bio link. ✨"
]

ENGAGEMENT_HOOKS = [
    "Would you have stopped him? 🫣",
    "What would you do if he looked at you like that? 🫦",
    "Would you run or would you stay? 🔥",
    "Rate this tension from 1-10 in the comments. 💬",
    "Who is really in control here? 🍷",
    "Could you say no to him? 🖤",
    "Drop a 🔥 if you felt that heartbeat."
]

def generate_offline_captions(video_name, dialogue_lines=None):
    """
    Generates 3 diverse, high-engagement X caption variants offline.
    """
    clean_title = os.path.splitext(os.path.basename(video_name))[0].replace("_", " ").title()
    quotes = [d.strip() for d in (dialogue_lines or []) if len(d.strip()) > 5]

    primary_quote = f'"{quotes[-1]}"' if quotes else '"Tell me to stop. Don\'t you dare."'
    second_quote = f'"{quotes[0]}"' if len(quotes) > 1 else '"Your heartbeat says otherwise."'

    # Pick 3 non-overlapping hashtag sets
    tag_sample = random.sample(HASHTAG_POOLS, 3)

    variants = []

    # Variant 1: In-character Quote & Tension Hook
    v1_cta = random.choice(CTA_POOLS)
    v1_hook = random.choice(ENGAGEMENT_HOOKS)
    v1_tags = " ".join(tag_sample[0])
    v1_text = (
        f"{primary_quote}\n\n"
        f"When boundaries blur after dark, nobody is walking away innocent. {v1_hook}\n\n"
        f"{v1_cta}\n{v1_tags}"
    )
    variants.append({
        "style": "In-Character Quote (Lời thoại cao trào)",
        "caption": v1_text
    })

    # Variant 2: Teasing Declarative Hook
    v2_cta = random.choice([c for c in CTA_POOLS if c != v1_cta])
    v2_hook = random.choice([h for h in ENGAGEMENT_HOOKS if h != v1_hook])
    v2_tags = " ".join(tag_sample[1])
    v2_text = (
        f"He thought he owned the room until she walked in. 🫦\n"
        f"One touch was all it took to lose complete control. {v2_hook}\n\n"
        f"{v2_cta}\n{v2_tags}"
    )
    variants.append({
        "style": "Teasing Tease (Khiêu khích & Giữ chân)",
        "caption": v2_text
    })

    # Variant 3: Spicy Question Hook
    v3_cta = random.choice([c for c in CTA_POOLS if c not in [v1_cta, v2_cta]])
    v3_hook = random.choice([h for h in ENGAGEMENT_HOOKS if h not in [v1_hook, v2_hook]])
    v3_tags = " ".join(tag_sample[2])
    v3_text = (
        f"Whispered promises and zero regrets. {second_quote} 🔥\n\n"
        f"Would you be able to resist, or would you give in right away? {v3_hook}\n\n"
        f"{v3_cta}\n{v3_tags}"
    )
    variants.append({
        "style": "Question Hook (Kích thích bình luận)",
        "caption": v3_text
    })

    return variants

def generate_captions_with_agy(video_path, dialogue_lines=None):
    """
    Attempts to use AGY CLI to generate captions if available,
    falling back seamlessly to offline generation.
    """
    from core.agy_connector import find_agy_executable
    agy = find_agy_executable()

    if not agy:
        return generate_offline_captions(video_path, dialogue_lines)

    quotes_str = ", ".join([f'"{d}"' for d in (dialogue_lines or [])[:4]])
    prompt = (
        f"Generate 3 spicy, short X/Twitter captions for short-drama clip: {os.path.basename(video_path)}. "
        f"Dialogue in video: {quotes_str}. Follow shadowban-avoidance: max 2-3 hashtags, rotate hooks, "
        f"engaging question at the end, suggestive tone, no explicit banned words."
    )

    try:
        res = subprocess.run([agy, "-p", prompt], capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and len(res.stdout.strip()) > 30:
            raw = res.stdout.strip()
            return [
                {"style": "AGY AI Generated Variant", "caption": raw}
            ]
    except Exception:
        pass

    return generate_offline_captions(video_path, dialogue_lines)

def save_captions_to_file(video_output_path, variants, dialogue_lines=None):
    """
    Saves generated caption variants into a readable text file alongside the output video.
    """
    base, _ = os.path.splitext(video_output_path)
    txt_path = f"{base}_X_captions.txt"

    lines = []
    lines.append("=======================================================")
    lines.append(f"  🎬 X/TWITTER SPICY CAPTIONS: {os.path.basename(video_output_path)}")
    lines.append("  (Chuẩn Shadowban-Avoidance • 2-3 Hashtags • Rotation CTA)")
    lines.append("=======================================================\n")

    if dialogue_lines:
        lines.append("📝 LỜI THOẠI TRÍCH XUẤT TỪ VIDEO:")
        for d in dialogue_lines[:5]:
            lines.append(f"  • {d}")
        lines.append("\n-------------------------------------------------------\n")

    for idx, v in enumerate(variants, 1):
        lines.append(f"📌 [OPTION {idx}] - {v['style']}")
        lines.append("-" * 45)
        lines.append(v['caption'])
        lines.append("\n" + "=" * 55 + "\n")

    lines.append("💡 LƯU Ý KHI ĐĂNG X/TWITTER:")
    lines.append("  1. Bật tính năng 'Mark media you post as sensitive' trong cài đặt X.")
    lines.append("  2. Đặt link xem phim đầy đủ trên Bio hoặc bài đăng chính, tránh spam link ở Reply.")
    lines.append("  3. Luân phiên chọn các Option khác nhau giữa các bài đăng liên tiếp.")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return txt_path
