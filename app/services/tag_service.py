from app.database import get_all_tags, get_tags, set_tags, get_all_tags_set


def list_all_tags():
    """Returns (filename->tags map, sorted list of all unique tags)."""
    tags_map = get_all_tags()
    all_tags = get_all_tags_set()
    return tags_map, all_tags


def get_file_tags(filename: str) -> list:
    return get_tags(filename)


def update_file_tags(filename: str, tags: list):
    if filename.startswith("upload:"):
        raise ValueError("上传文件暂不保存标签")
    set_tags(filename, tags)
