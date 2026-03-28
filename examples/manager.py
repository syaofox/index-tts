import json
import os
import shutil
import time


EXAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))
CASES_FILE = os.path.join(EXAMPLES_DIR, "cases.jsonl")
USER_DIR = os.path.join(EXAMPLES_DIR, "user")
USER_CASES_FILE = os.path.join(USER_DIR, "user_cases.jsonl")
USER_EMO_DIR = os.path.join(USER_DIR, "emo")


def _ensure_dirs():
    os.makedirs(USER_DIR, exist_ok=True)
    os.makedirs(USER_EMO_DIR, exist_ok=True)


def _load_jsonl(filepath):
    """从 JSONL 文件加载数据"""
    items = []
    if not os.path.exists(filepath):
        return items
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _save_jsonl(filepath, items):
    """将数据写入 JSONL 文件"""
    with open(filepath, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_official_examples():
    """加载官方示例 (cases.jsonl)，只读"""
    return _load_jsonl(CASES_FILE)


def load_user_examples():
    """加载用户自定义示例 (user/user_cases.jsonl)"""
    return _load_jsonl(USER_CASES_FILE)


def load_all_examples():
    """加载所有示例：官方 + 用户自定义，返回 (列表, 官方数量)"""
    official = load_official_examples()
    user = load_user_examples()
    return official + user, len(official)


def save_user_examples(examples):
    """将用户示例列表写回 user/user_cases.jsonl"""
    _ensure_dirs()
    _save_jsonl(USER_CASES_FILE, examples)


def _safe_filename(name, ext=".wav"):
    """清理文件名，返回安全的文件名"""
    safe = "".join(c for c in name if c.isalnum() or c in "-_ ")
    safe = safe.strip().replace(" ", "_")
    return f"{safe}{ext}" if safe else f"audio_{int(time.time() * 1000)}{ext}"


def _unique_path(directory, filename):
    """确保文件名不冲突，返回完整路径"""
    dst = os.path.join(directory, filename)
    if not os.path.exists(dst):
        return dst
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(dst):
        dst = os.path.join(directory, f"{base}_{counter}{ext}")
        counter += 1
    return dst


def copy_prompt_audio(src_path, custom_name=None):
    """复制音色参考音频到 user/ 目录，文件存在时覆盖"""
    if not src_path or not os.path.exists(src_path):
        return None
    _ensure_dirs()
    ext = os.path.splitext(src_path)[1] or ".wav"
    if custom_name:
        filename = _safe_filename(custom_name, ext)
        dst = os.path.join(USER_DIR, filename)
        shutil.copy2(src_path, dst)
        return os.path.join("user", filename)
    # 未指定名称，自动生成
    filename = f"prompt_{int(time.time() * 1000)}{ext}"
    dst = os.path.join(USER_DIR, filename)
    shutil.copy2(src_path, dst)
    return os.path.join("user", filename)


def copy_emo_audio(src_path, custom_name=None):
    """复制情感参考音频到 user/emo/ 目录，文件存在时覆盖"""
    if not src_path or not os.path.exists(src_path):
        return None
    _ensure_dirs()
    ext = os.path.splitext(src_path)[1] or ".wav"
    if custom_name:
        filename = _safe_filename(custom_name, ext)
        dst = os.path.join(USER_EMO_DIR, filename)
        shutil.copy2(src_path, dst)
        return os.path.join("user/emo", filename)
    # 未指定名称，自动生成
    filename = f"emo_{int(time.time() * 1000)}{ext}"
    dst = os.path.join(USER_EMO_DIR, filename)
    shutil.copy2(src_path, dst)
    return os.path.join("user/emo", filename)


def get_emo_audio_choices():
    """获取已保存的情感参考音频列表，返回 [(文件名, 相对路径)]"""
    _ensure_dirs()
    choices = []
    if not os.path.exists(USER_EMO_DIR):
        return choices
    for f in sorted(os.listdir(USER_EMO_DIR)):
        if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
            name = os.path.splitext(f)[0]
            rel_path = os.path.join("user/emo", f)
            choices.append((name, rel_path))
    return choices


def get_prompt_audio_choices():
    """获取已保存的音色参考音频列表，返回 [(文件名, 相对路径)]"""
    _ensure_dirs()
    choices = []
    if not os.path.exists(USER_DIR):
        return choices
    for f in sorted(os.listdir(USER_DIR)):
        if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
            name = os.path.splitext(f)[0]
            rel_path = os.path.join("user", f)
            choices.append((name, rel_path))
    return choices


def add_user_example(example_data):
    """添加新用户示例，返回在用户列表中的索引"""
    examples = load_user_examples()
    examples.append(example_data)
    save_user_examples(examples)
    return len(examples) - 1


def delete_user_example(user_index):
    """删除指定索引的用户示例及其音色参考音频，返回是否成功"""
    examples = load_user_examples()
    if user_index < 0 or user_index >= len(examples):
        return False
    ex = examples[user_index]
    # 删除音色参考音频文件
    prompt_audio = ex.get("prompt_audio", "")
    if prompt_audio:
        audio_path = os.path.join(EXAMPLES_DIR, prompt_audio)
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass
    examples.pop(user_index)
    save_user_examples(examples)
    return True


def update_user_example(user_index, example_data):
    """更新指定索引的用户示例，返回是否成功"""
    examples = load_user_examples()
    if user_index < 0 or user_index >= len(examples):
        return False
    examples[user_index] = example_data
    save_user_examples(examples)
    return True


def get_user_example_display_list():
    """返回用户示例的下拉选择列表 [(label, user_index)]"""
    examples = load_user_examples()
    result = []
    for i, ex in enumerate(examples):
        # 使用参考音频文件名作为前缀
        prompt_audio = ex.get("prompt_audio", "")
        if prompt_audio:
            prefix = os.path.splitext(os.path.basename(prompt_audio))[0]
        else:
            prefix = f"#{i + 1}"
        text = ex.get("text", "")
        label = f"[{prefix}] {text[:25]}{'...' if len(text) > 25 else ''}"
        result.append((label, i))
    return result
